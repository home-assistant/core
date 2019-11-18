#!/bin/sh
apt update 
apt upgrade -y 
apt install pkg-config -y 
echo "19.11.06" > /data/data/pl.sviete.dom/files/home/AIS/.ais_apt
