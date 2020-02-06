#!/bin/sh
apt update 
apt upgrade -y 
curl -o "/data/data/pl.sviete.dom/files/home/.bash_profile" -L  https://raw.githubusercontent.com/sviete/AIS-utils/master/patches/scripts/.bash_profile 
chmod +x /data/data/pl.sviete.dom/files/home/.bash_profile 
echo "20.01.14" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt
