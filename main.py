import threading
import time
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from app import wifi_manager
import subprocess
import requests
import socket
import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = os.urandom(24)

periodic_thread = None
periodic_stop_flag = threading.Event()
last_error_time = None  # Simpan waktu error terakhir
hotspot_active = False

# --- OLED SETUP (hotswap safe, 128x64) ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
font_size = 11  # Ubah ke 11 agar proporsional untuk 128x64
if os.path.exists(FONT_PATH):
    font = ImageFont.truetype(FONT_PATH, font_size)
else:
    font = ImageFont.load_default()

def init_oled():
    try:
        # Selalu buat objek I2C baru!
        i2c = busio.I2C(board.SCL, board.SDA)
        # Tunggu I2C ready (jika baru dicolok)
        while not i2c.try_lock():
            time.sleep(0.05)
        i2c.unlock()
        oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
        return oled
    except Exception as e:
        print("OLED not detected:", e)
        return None

oled = init_oled()

def draw_oled(ap_label, ap_content, ip, status_label, status_content, log_label, log_content, scroll_pos_ap=0, scroll_pos_status=0, scroll_pos_log=0):
    width = oled.width if oled else 128
    height = oled.height if oled else 64
    image = Image.new("1", (width, height))
    draw = ImageDraw.Draw(image)

    # Baris 1: AP/SSID
    ap_label_width = int(font.getlength(ap_label)-4)
    ap_content_x = ap_label_width + 1
    draw.text((0, 0), ap_label, font=font, fill=255)
    ap_content_full = ap_content + " "
    ap_content_width = int(font.getlength(ap_content_full))
    content_area_width = width - ap_content_x

    ap_content_img = Image.new("1", (content_area_width, font_size+2))
    ap_content_draw = ImageDraw.Draw(ap_content_img)
    if ap_content_width > content_area_width:
        scroll_range = ap_content_width + content_area_width
        scroll_offset = scroll_pos_ap % scroll_range
        x = content_area_width - scroll_offset
        ap_content_draw.text((x, 0), ap_content_full, font=font, fill=255)
    else:
        ap_content_draw.text((0, 0), ap_content, font=font, fill=255)
    image.paste(ap_content_img, (ap_content_x, 0))

    # Baris 2: IP/Host
    draw.text((0, 16), ip, font=font, fill=255)

    # Baris 3: Status
    status_label_width = int(font.getlength(status_label)-4)
    status_content_x = status_label_width + 1
    draw.text((0, 32), status_label, font=font, fill=255)
    status_content_full = status_content + " "
    status_content_width = int(font.getlength(status_content_full))
    status_area_width = width - status_content_x

    status_content_img = Image.new("1", (status_area_width, font_size+2))
    status_content_draw = ImageDraw.Draw(status_content_img)
    if status_content_width > status_area_width:
        scroll_range = status_content_width + status_area_width
        scroll_offset = scroll_pos_status % scroll_range
        x = status_area_width - scroll_offset
        status_content_draw.text((x, 0), status_content_full, font=font, fill=255)
    else:
        status_content_draw.text((0, 0), status_content, font=font, fill=255)
    image.paste(status_content_img, (status_content_x, 32))

    # Baris 4: Log
    log_label_width = int(font.getlength(log_label)-4)
    log_content_x = log_label_width + 1
    draw.text((0, 48), log_label, font=font, fill=255)
    log_content_full = log_content + " "
    log_content_width = int(font.getlength(log_content_full))
    log_area_width = width - log_content_x

    log_content_img = Image.new("1", (log_area_width, font_size+2))
    log_content_draw = ImageDraw.Draw(log_content_img)
    if log_content_width > log_area_width:
        scroll_range = log_content_width + log_area_width
        scroll_offset = scroll_pos_log % scroll_range
        x = log_area_width - scroll_offset
        log_content_draw.text((x, 0), log_content_full, font=font, fill=255)
    else:
        log_content_draw.text((0, 0), log_content, font=font, fill=255)
    image.paste(log_content_img, (log_content_x, 48))

    return image

def safe_draw_oled(ap_label, ap_content, ip, status_label, status_content, log_label, log_content, scroll_pos_ap=0, scroll_pos_status=0, scroll_pos_log=0):
    global oled
    try:
        if oled is None:
            oled = init_oled()
        if oled is not None:
            image = draw_oled(ap_label, ap_content, ip, status_label, status_content, log_label, log_content, scroll_pos_ap, scroll_pos_status, scroll_pos_log)
            oled.image(image)
            oled.show()
    except Exception as e:
        print("OLED error:", e)
        oled = None

def send_periodic(api_token, scheme_id, script_path, interval, raspiot_url):
    global periodic_stop_flag, last_error_time
    while not periodic_stop_flag.is_set():
        if not wifi_manager.is_connected():
            last_error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            periodic_stop_flag.set()
            wifi_manager.enable_hotspot()
            break
        try:
            result = subprocess.check_output([script_path], timeout=10)
            lines = result.decode().splitlines()
            values = lines[0] if lines else ""
            additional = {}
            if len(lines) > 1:
                for pair in lines[1].split(';'):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        additional[k.strip()] = v.strip()
            payload = {
                "api_key": api_token,
                "scheme_id": scheme_id,
                "values": values,
                "additional_values": additional
            }
            requests.post(raspiot_url, json=payload, timeout=10)
        except Exception as e:
            last_error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            periodic_stop_flag.set()
            wifi_manager.enable_hotspot()
            break
        time.sleep(interval)

def monitor_connection():
    global periodic_stop_flag, last_error_time, hotspot_active
    while True:
        if not hotspot_active:
            if not wifi_manager.is_connected():
                # Saat koneksi hilang
                last_error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                periodic_stop_flag.set()
                wifi_manager.enable_hotspot()
                set_oled_status("System Offline, Connection Lost -- Hotspot Activated")
                hotspot_active = True
        time.sleep(5)  # cek setiap 5 detik

@app.route('/', methods=['GET', 'POST'])
def wifi_setup():
    global hotspot_active
    global last_error_time
    error_message = None
    if last_error_time:
        error_message = f"Pengiriman data sebelumnya gagal pada {last_error_time} karena koneksi hilang."
        last_error_time = None  # Reset setelah ditampilkan

    if wifi_manager.is_connected():
        return redirect(url_for('run_program'))

    if request.method == 'POST':
        ssid = request.form['ssid']
        password = request.form['password']
        success = wifi_manager.connect_wifi(ssid, password)
        # Setelah sukses connect WiFi
        if success:
            redirect('http://raspiot/')
            time.sleep(1)
            wifi_manager.disable_hotspot()
            hotspot_active = False  
            flash('WiFi connected successfully!', 'success')
            set_oled_status("System Online")
            return
        else:
            flash('Failed to connect WiFi. Please try again.', 'danger')

    ssids = wifi_manager.scan_wifi()
    return render_template('wifi_setup.html', ssids=ssids, error_message=error_message)

@app.route('/run', methods=['GET', 'POST'])
def run_program():
    global periodic_thread, periodic_stop_flag, last_error_time
    output = None
    api_token = scheme_id = script_path = mode = interval = ""
    additional = {}

    if request.method == 'POST':
        api_token = request.form.get('api_token', '')
        scheme_id = request.form.get('scheme_id', '')
        script_path = request.form.get('script_path', '')
        mode = request.form.get('mode', 'once')
        interval = request.form.get('interval', '')
        action = request.form.get('action', '')

        if action == "test":
            # Jalankan script user dan ambil output
            try:
                result = subprocess.check_output([script_path], timeout=10)
                lines = result.decode().splitlines()
                output = lines[0] if lines else ""
                # Parse additional_values jika ada baris kedua
                if len(lines) > 1:
                    for pair in lines[1].split(';'):
                        if '=' in pair:
                            k, v = pair.split('=', 1)
                            additional[k.strip()] = v.strip()
            except Exception as e:
                flash(f'Gagal menjalankan script: {e}', 'danger')
                output = ""
        elif action == "send":
            # Kirim data ke server raspiot
            output = request.form.get('values', '')
            # Ambil additional_values dari hidden input jika ada
            additional = {}
            for key in request.form:
                if key.startswith('additional_'):
                    k = key.replace('additional_', '')
                    additional[k] = request.form[key]
            # Atau, jika ingin tetap parsing dari output, bisa juga

            # Siapkan payload
            payload = {
                "api_key": api_token,
                "scheme_id": scheme_id,
                "values": output,
                "additional_values": additional
            }
            # Ganti URL berikut dengan endpoint server raspiot kamu
            raspiot_url = "http://robotika.upnvj.ac.id:8080/api/data"
            try:
                if mode == "periodic":
                    try:
                        interval_sec = int(interval)
                        periodic_stop_flag.clear()
                        periodic_thread = threading.Thread(
                            target=send_periodic,
                            args=(api_token, scheme_id, script_path, interval_sec, raspiot_url),
                            daemon=True
                        )
                        periodic_thread.start()
                        set_oled_status("Running Periodic Data Transfer Job")
                        flash('Pengiriman data periodik telah dimulai!', 'success')
                    except Exception as e:
                        flash(f'Gagal memulai mode periodik: {e}', 'danger')
                else:
                    resp = requests.post(raspiot_url, json=payload, timeout=10)
                    if resp.status_code == 201:
                        flash(f'Data berhasil dikirim ke server! Response: {resp.text}', 'success')
                    else:
                        flash(f'Gagal kirim data: {resp.text}', 'danger')
            except Exception as e:
                flash(f'Gagal kirim data: {e}', 'danger')

    is_periodic_running = periodic_thread is not None and periodic_thread.is_alive()
    error_message = None
    if last_error_time:
        error_message = f"Pengiriman data sebelumnya gagal pada {last_error_time} karena koneksi hilang."
        last_error_time = None  # Reset setelah ditampilkan
    return render_template(
        'run_program.html',
        output=output,
        api_token=api_token,
        scheme_id=scheme_id,
        script_path=script_path,
        mode=mode,
        interval=interval,
        additional=additional,
        is_periodic_running=is_periodic_running,
        error_message=error_message
    )

def get_last_journal_line():
    try:
        # Ambil 5 baris terakhir, cari yang bukan logo/favicon
        output = subprocess.check_output(
            ["journalctl", "-u", "raspiot-client.service", "-n", "5", "--no-pager"],
            stderr=subprocess.DEVNULL
        )
        lines = output.decode(errors="ignore").strip().split('\n')
        for line in reversed(lines):
            if "logo" in line.lower() or "favicon" in line.lower():
                continue
            # Hapus timestamp jika ada
            if "raspiot-client.service:" in line:
                line = line.split("raspiot-client.service:")[-1].strip()
            if line.strip():
                return line
        return ""
    except Exception:
        return ""

@app.route('/stop', methods=['POST'])
def stop_periodic():
    global periodic_stop_flag, periodic_thread
    periodic_stop_flag.set()
    if periodic_thread and periodic_thread.is_alive():
        periodic_thread.join(timeout=2)
    # Pastikan variabel thread direset jika sudah mati
    if periodic_thread and not periodic_thread.is_alive():
        periodic_thread = None
    set_oled_status("Periodic Job Stopped", hold=5)
    flash('Periodic sender stopped.', 'success')
    return redirect(url_for('run_program'))

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = 'No IP'
    finally:
        s.close()
    return ip

def get_nm_status():
    try:
        out = subprocess.check_output(['nmcli', '-t', '-f', 'active,ssid,mode', 'dev', 'wifi'], encoding='utf-8')
        for line in out.splitlines():
            if line.startswith('yes:'):
                parts = line.strip().split(':')
                if len(parts) >= 3:
                    return parts[1], parts[2]  # ssid, mode
    except Exception:
        pass
    return None, None

def get_hotspot_password():
    try:
        out = subprocess.check_output(['nmcli', '-s', '-g', '802-11-wireless-security.psk', 'connection', 'show', 'Hotspot'], encoding='utf-8')
        return out.strip()
    except Exception:
        return "raspiot"

def get_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return "raspiot"

def oled_updater():
    global oled_scroll_ap, oled_scroll_status, oled_scroll_log, oled_status_app
    last_ap_content = ""
    last_status_content = ""
    last_log_content = ""
    oled_scroll_ap = 0
    oled_scroll_status = 0
    oled_scroll_log = 0
    display_mode = "ip"
    last_switch = time.time()
    while True:
        ip_addr = get_ip()
        hostname = get_hostname()
        now = time.time()
        # Baris 2: IP/Host
        if ip_addr == "10.0.0.1":
            baris_ip = f"IP:{ip_addr}"
            display_mode = "ip"
            last_switch = now
        else:
            if display_mode == "ip" and now - last_switch > 10:
                display_mode = "host"
                last_switch = now
            elif display_mode == "host" and now - last_switch > 5:
                display_mode = "ip"
                last_switch = now
            baris_ip = f"IP:{ip_addr}" if display_mode == "ip" else f"Host:{hostname}"

        ssid, mode = get_nm_status()
        ap_label = "AP: "
        if ip_addr == "10.0.0.1":
            ap_content = f"{ssid}/{get_hotspot_password()}"
        else:
            ap_content = f"{ssid}" if ssid else "-"

        status_label = "Status: "
        status_app = globals().get("oled_status_app", "Standby")

        log_label = "Log: "
        logline = get_last_journal_line()

        if ap_content != last_ap_content:
            oled_scroll_ap = 0
            last_ap_content = ap_content
        if status_app != last_status_content:
            oled_scroll_status = 0
            last_status_content = status_app
        if logline != last_log_content:
            oled_scroll_log = 0
            last_log_content = logline

        safe_draw_oled(
            ap_label, ap_content, baris_ip,
            status_label, status_app,
            log_label, logline,
            oled_scroll_ap, oled_scroll_status, oled_scroll_log
        )
        oled_scroll_ap += 8
        oled_scroll_status += 8
        oled_scroll_log += 8
        time.sleep(0.016)

# Jalankan thread OLED saat aplikasi start
threading.Thread(target=oled_updater, daemon=True).start()

def set_oled_status(new_status, hold=0):
    globals()["oled_status_app"] = new_status
    if hold > 0:
        # Kembalikan ke status default setelah hold detik
        def reset_status():
            time.sleep(hold)
            # Hanya reset jika status belum berubah
            if globals().get("oled_status_app") == new_status:
                update_status_by_condition()
        threading.Thread(target=reset_status, daemon=True).start()

def update_status_by_condition():
    ip_addr = get_ip()
    if ip_addr == "10.0.0.1":
        if last_error_time:
            set_oled_status("System Offline, Connection Lost -- Hotspot Activated")
        else:
            set_oled_status("System Offline -- Hotspot Active")
    else:
        if periodic_thread and periodic_thread.is_alive():
            set_oled_status("Running Periodic Data Transfer Job")
        else:
            set_oled_status("System Online")

if __name__ == '__main__':
    threading.Thread(target=monitor_connection, daemon=True).start()
    if not wifi_manager.is_connected():
        wifi_manager.enable_hotspot()
        set_oled_status("System Offline -- Hotspot Active")
    else:
        update_status_by_condition() 
    app.run(host='0.0.0.0', port=80)