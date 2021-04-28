#!/bin/sh
echo "AIS release script starting for 21.02.19 on chanel 3" 
apt update 

apt upgrade  -y 

apt reinstall python 

curl -o "/sdcard/AisLauncher.apk" -L https://powiedz.co/ota/android/AisLauncher.apk 

su -c "pm install -r /sdcard/AisLauncher.apk" 

echo "# AIS Config file for mosquitto" > "/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf"  

echo "listener 1883 0.0.0.0" >> "/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf"  

echo "allow_anonymous true" >> "/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf"  

echo "21.03.24" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt  

