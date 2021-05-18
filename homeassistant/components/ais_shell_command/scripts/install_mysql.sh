#!/data/data/pl.sviete.dom/files/usr/bin/sh
echo "Install mariadb..."
apt install mariadb

echo "Start as service"
mysqld_safe -u root
mysql -u $(whoami)

create user ais@localhost IDENTIFIED BY dom;
create database dom;
grant all privileges on dom to 'ais'@'%' with grant option;




echo "Done!"

