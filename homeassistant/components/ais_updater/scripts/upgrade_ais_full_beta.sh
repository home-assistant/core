#!/data/data/pl.sviete.dom/files/usr/bin/sh
echo "--------------------------------" >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
echo "UPDATE AIS dom, linux and python" >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
echo $(date '+%Y %b %d %H:%M') start >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
echo "Step 1 update the AIS dom Linux box" >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
apt update >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
apt upgrade -y >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt

echo "Step 2 update the AIS dom python app" >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
pip install ais_dom -U >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt

echo "Step 3 update the android app and restart" >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
am start -n launcher.sviete.pl.domlauncherapp/.LauncherActivity -e command ais-dom-update-beta >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt

echo "Step 4 pm2 restart ais" >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
pm2 restart ais >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt

echo $(date '+%Y %b %d %H:%M') end >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
echo " " >> /data/data/pl.sviete.dom/files/home/AIS/www/upgrade_log.txt
