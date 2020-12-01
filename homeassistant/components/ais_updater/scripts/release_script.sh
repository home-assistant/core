#!/bin/sh
echo "AIS release script starting for 20.10.07 on chanel 2" 
curl -o "/sdcard/AisClient.apk" -L https://powiedz.co/ota/android/AisDomApp-client-gate-release.apk && su -c "pm install -r /sdcard/AisClient.apk" 

echo "20.11.24" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt
