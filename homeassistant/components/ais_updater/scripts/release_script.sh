#!/bin/sh
echo "AIS START"; 
echo "AIS remove data from tmp"; 
su -c "rm -rf /data/data/pl.sviete.dom/files/usr/tmp/*" 
echo "New zigbee frontend"; 
curl https://raw.githubusercontent.com/sviete/AIS-utils/master/patches/add_zigbee_frontend.sh | bash 
echo "AIS DomApp-client-gate-release.apk"; 
curl -o "/sdcard/AisClient.apk" -L https://powiedz.co/ota/android/AisDomApp-client-gate-release.apk && su -c "pm install -r /sdcard/AisClient.apk" 
echo "20.10.07" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt
