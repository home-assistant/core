#!/bin/sh
echo "AIS release script starting for 21.04.25 on chanel 2" 
echo "AIS Linux update START" 

echo "AIS save config file for mosquitto" 

cp /data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf /sdcard/mosquitto.conf 

echo "AIS apt update" 

apt update 

DEBIAN_FRONTEND=noninteractive apt -y upgrade 

echo "AIS back config file for mosquitto" 

cp /sdcard/mosquitto.conf /data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf 

echo "AIS reinstall python" 

apt reinstall python 

pip install python-miio==0.5.5 -U  

echo "AIS Linux update END" 

echo "21.05.25" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt  

