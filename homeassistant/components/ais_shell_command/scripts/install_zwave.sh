#!/data/data/pl.sviete.dom/files/usr/bin/sh
echo "Stopping zwavejs2mqtt..."
pm2 stop zwave

echo "Delete old version..."
rm -rf ~/zwavejs2mqtt

echo "Clone new version..."
cd ~
git clone --depth=1 https://github.com/zwave-js/zwavejs2mqtt.git

echo "Cd to dir..."
cd ~/zwavejs2mqtt

echo "Installing dependencies..."
npm ci --unsafe-perm

echo "Starting zwavejs2mqtt..."
pm2 start zwave


echo "Done!"

