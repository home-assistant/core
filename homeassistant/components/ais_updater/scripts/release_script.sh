#!/bin/sh
echo "AIS release script starting for 21.03.24 on chanel 2" 
pip install python-miio==0.5.5 -U  

echo "21.04.08" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt  
apt update 

DEBIAN_FRONTEND=noninteractive apt -y upgrade 

apt reinstall python 

pip install python-miio==0.5.5 -U  

echo "21.05.18" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt  

