#!/data/data/pl.sviete.dom/files/usr/bin/sh
echo "Install mariadb..."
apt install mariadb

echo "Start as service"
mysqld_safe -u root
mysql -u $(whoami)

apt install mariadb
mysql_install_db
mysql -u $(whoami) --execute="CREATE DATABASE ha CHARACTER SET utf8;"
mysql -u $(whoami) --execute="CREATE USER 'ais'@'localhost' IDENTIFIED  BY 'dom';"
mysql -u $(whoami) --execute="GRANT ALL PRIVILEGES ON ha.* TO 'ais'@'localhost';"
# test
mysql -h 127.0.0.1 -u ais -pdom ha --execute="select 'DB TEST OK' as ais from dual;"

echo "Done!"

