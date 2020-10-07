#!/bin/sh
echo "AIS START"; 
echo "AIS remove data from tmp"; 
su -c "rm -rf /data/data/pl.sviete.dom/files/usr/tmp/*" 
echo "create .bashrc"; 
curl -o "/data/data/pl.sviete.dom/files/home/.bashrc"  -L https://raw.githubusercontent.com/sviete/AIS-utils/master/patches/.bashrc 
echo "Change generic key layout"; 
curl https://raw.githubusercontent.com/sviete/AIS-utils/master/linux/update_ais_keylayout.sh | bash 
echo "20.08.17" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt
