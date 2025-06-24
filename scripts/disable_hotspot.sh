#!/bin/bash

sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
sudo systemctl start NetworkManager