#!/data/data/pl.sviete.dom/files/usr/bin/sh
echo "Stopping zigbee2mqtt..."
pm2 stop zigbee

echo "Creating backup of configuration..."
cp -R ~/zigbee2mqtt/data/configuration.yaml ~/configuration.yaml

echo "Delete old version..."
rm -rf ~/zigbee2mqtt

echo "Clone new version..."
git clone --depth=1 https://github.com/Koenkk/zigbee2mqtt.git

echo "Cd to dir..."
cd ~/zigbee2mqtt

echo "Updating..."
git checkout HEAD -- npm-shrinkwrap.json
git pull

echo "Installing dependencies..."
npm ci --unsafe-perm

echo "Restore configuration..."
cp ~/configuration.yaml ~/zigbee2mqtt/data/configuration.yaml
rm ~/configuration.yaml

echo "zip"
cd ~
7za a -mmt=2 ~/zigbee.zip ~/zigbee2mqtt/.

echo "Starting zigbee2mqtt..."
pm2 start zigbee


echo "Done!"

# publih to ota
# scp -P 7777 zigbee.zip dom@147.135.209.212:/var/www/AIS-WWW/ota/zigbee_beta.zip
# scp -P 7777 zigbee.zip dom@147.135.209.212:/var/www/AIS-WWW/ota/zigbee.zip

echo "!!! PUT  zigbee.zip in AIS-WWW !!!"
echo "!!! PUT  zigbee.zip in AIS-WWW !!!"
echo "!!! PUT  zigbee.zip in AIS-WWW !!!"


# to test restore
# rm -rf ~/zigbee2mqtt
# 7z x -mmt=2 -o/data/data/pl.sviete.dom/files/home/zigbee2mqtt ~/zigbee.zip -y

# the configuration.yaml should be
#homeassistant: true
#permit_join: false
#mqtt:
#  base_topic: zigbee2mqtt
#  server: 'mqtt://localhost'
#serial:
#  port: /dev/ttyACM0
#advanced:
#  log_level: info
#  log_output:
#    - console
#frontend:
#  port: 8099
#experimental:
#  new_api: true

