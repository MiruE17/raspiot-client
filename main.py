import threading
import time
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from app import wifi_manager

app = Flask(__name__)
app.secret_key = os.urandom(24)

periodic_thread = None
periodic_stop_flag = threading.Event()
last_error_time = None  # Simpan waktu error terakhir
hotspot_active = False

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
                last_error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                periodic_stop_flag.set()
                wifi_manager.enable_hotspot()
                hotspot_active = True
        time.sleep(5)  # cek setiap 5 detik

@app.route('/', methods=['GET', 'POST'])
def wifi_setup():
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
        # Setelah berhasil connect WiFi
        if success:
            wifi_manager.disable_hotspot()
            hotspot_active = False
            flash('WiFi connected successfully!', 'success')
            return redirect(url_for('run_program'))
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
                        flash('Pengiriman data periodik telah dimulai!', 'success')
                    except Exception as e:
                        flash(f'Gagal memulai mode periodik: {e}', 'danger')
                else:
                    resp = requests.post(raspiot_url, json=payload, timeout=10)
                    if resp.status_code == 200:
                        flash('Data berhasil dikirim ke server!', 'success')
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

@app.route('/stop', methods=['POST'])
def stop_periodic():
    global periodic_stop_flag
    periodic_stop_flag.set()
    flash('Periodic sender stopped.', 'success')
    return redirect(url_for('run_program'))

if __name__ == '__main__':
    threading.Thread(target=monitor_connection, daemon=True).start()
    if not wifi_manager.is_connected():
        wifi_manager.enable_hotspot()
    app.run(host='0.0.0.0', port=80)