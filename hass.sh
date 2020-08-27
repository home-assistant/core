#!/usr/bin/env bash

source "/home/andrzej/Projects/AIS-home-assistant/venv/bin/activate"
python3.7 /home/andrzej/Projects/AIS-home-assistant/homeassistant/__main__.py -c /data/data/pl.sviete.dom/files/home/AIS/

# pm2 start hass.sh --name ais-demo --restart-delay=30000
# pm2 start lt  --name demo-tunnel -- -h http://paczka.pro -p 8180 -s demo
