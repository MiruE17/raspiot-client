import subprocess

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

def is_connected():
    """Cek apakah sudah terkoneksi ke internet."""
    try:
        subprocess.check_call(['ping', '-c', '1', '-W', '2', '8.8.8.8'])
        return True
    except subprocess.CalledProcessError:
        return False

def enable_hotspot():
    """Aktifkan hotspot dengan nmcli."""
    try:
        subprocess.check_call([
            'nmcli', 'device', 'wifi', 'hotspot',
            'ifname', 'wlan0',
            'ssid', 'RaspIoT',
            'password', 'rasp-iot'
        ])
        return True
    except subprocess.CalledProcessError:
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