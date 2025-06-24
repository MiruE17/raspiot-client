#!/bin/bash

SSID="RaspIoT"
PASS="raspiot"

# Stop NetworkManager jika perlu
sudo systemctl stop NetworkManager

# Konfigurasi hostapd
cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=$SSID
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASS
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Set IP static untuk wlan0
sudo ifconfig wlan0 192.168.4.1 netmask 255.255.255.0

# Start hostapd dan dnsmasq
sudo systemctl start hostapd
sudo systemctl start dnsmasq