#!/bin/sh
echo "AIS release script starting for 21.01.14 on chanel 2" 
apt update 

apt upgrade  -y 

curl -o "/data/data/pl.sviete.dom/files/home/.bash_profile" -L  https://raw.githubusercontent.com/sviete/AIS-utils/master/patches/scripts/.bash_profile 

curl -o "/sdcard/AisClient.apk" -L https://powiedz.co/ota/android/AisPanelApp-gate-release.apk && su -c "pm install -r /sdcard/AisClient.apk" 

echo "21.01.29" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt
