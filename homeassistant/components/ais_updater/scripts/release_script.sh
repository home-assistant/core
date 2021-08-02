#!/bin/sh
echo "AIS release script starting for 21.07.02 on chanel 2" 
echo "Switch AIS repo"  

echo "# The main AI-Speaker repository:" > /data/data/pl.sviete.dom/files/usr/etc/apt/sources.list 

echo "deb [trusted=yes] https://powiedz.co/apt dom stable" >> /data/data/pl.sviete.dom/files/usr/etc/apt/sources.list 

echo "deb [trusted=yes] https://powiedz.co/apt python 3.9" >> /data/data/pl.sviete.dom/files/usr/etc/apt/sources.list 


apt update 

DEBIAN_FRONTEND=noninteractive apt -y upgrade 

DEBIAN_FRONTEND=noninteractive apt install -y cloudflared 


pip install av==8.0.3 -U  

echo "21.07.15" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt  

