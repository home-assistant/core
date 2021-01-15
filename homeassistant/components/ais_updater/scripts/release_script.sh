#!/bin/sh
echo "AIS release script starting for 21.01.06 on chanel 2" 
apt update 

apt upgrade  -y 

echo "21.01.14" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt
