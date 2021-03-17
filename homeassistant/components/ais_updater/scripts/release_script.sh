#!/bin/sh
echo "AIS release script starting for 21.03.01 on chanel 2" 
curl -o "/sdcard/AisLauncher.apk" -L https://powiedz.co/ota/android/AisLauncher.apk 

su -c "pm install -r /sdcard/AisLauncher.apk" 

echo "21.03.12" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt  

