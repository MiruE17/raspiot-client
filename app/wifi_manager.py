import subprocess
import time

def scan_wifi():
    """Scan WiFi SSID di sekitar."""
    try:
        result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi'])
        ssids = set(line.decode().strip() for line in result.splitlines() if line.strip())
        return sorted(ssids)
    except Exception as e:
        return []

def connect_wifi(ssid, password):
    """Connect ke WiFi dengan nmcli."""
    try:
        subprocess.check_call(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password])
        return True
    except subprocess.CalledProcessError:
        return False

def is_connected(retry=5, timeout=2):
    """Cek koneksi internet dengan ping 8.8.8.8 beberapa kali."""
    success = 0
    for _ in range(retry):
        try:
            subprocess.check_call(['ping', '-c', '1', '-W', str(timeout), '8.8.8.8'],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            success += 1
        except subprocess.CalledProcessError:
            pass
    return success > 0

def enable_hotspot(max_retry=5, delay=2):
    """Aktifkan hotspot dengan nmcli. Coba terus sampai berhasil atau mencapai max_retry."""
    for attempt in range(max_retry):
        try:
            subprocess.check_call([
                'nmcli', 'device', 'wifi', 'hotspot',
                'ifname', 'wlan0',
                'ssid', 'RaspIoT',
                'password', '12345678'
            ])
            try:
                subprocess.check_call([
                    'nmcli', 'connection', 'up', 'Hotspot'
                ])
                return True
            except subprocess.CalledProcessError:
                # Jika gagal, coba matikan dan nyalakan ulang hotspot sekali lagi
                subprocess.call(['nmcli', 'connection', 'down', 'Hotspot'])
                subprocess.check_call([
                    'nmcli', 'device', 'wifi', 'hotspot',
                    'ifname', 'wlan0',
                    'ssid', 'RaspIoT',
                    'password', 'rasp-iot'
                ])
                subprocess.check_call([
                    'nmcli', 'connection', 'up', 'Hotspot'
                ])
                return True
        except subprocess.CalledProcessError:
            time.sleep(delay)
            continue
    return False

def disable_hotspot():
    """Nonaktifkan hotspot nmcli."""
    try:
        subprocess.check_call([
            'nmcli', 'connection', 'down', 'Hotspot'
        ])
        return True
    except subprocess.CalledProcessError:
        return False