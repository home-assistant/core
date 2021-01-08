#!/bin/sh
echo "AIS release script starting for 20.11.24 on chanel 2" 
curl -o "/sdcard/AisClient.apk" -L https://powiedz.co/ota/android/AisDomApp-client-gate-release.apk && su -c "pm install -r /sdcard/AisClient.apk" 

echo "21.01.06" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt
