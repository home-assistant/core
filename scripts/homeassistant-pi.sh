#!/bin/sh

# To script is for running Home Assistant as a service and automatically starting it on boot.
# Assuming you have cloned the HA repo into /home/pi/Apps/home-assistant adjust this path if necessary
# This also assumes you installed HA on your raspberry pi using the instructions here:
# https://home-assistant.io/getting-started/
#
# To install to the following:
# sudo cp /home/pi/Apps/home-assistant/scripts/homeassistant-pi.sh /etc/init.d/homeassistant.sh
# sudo chmod +x /etc/init.d/homeassistant.sh
# sudo chown root:root /etc/init.d/homeassistant.sh
#
# If you want HA to start on boot also run the following:
# sudo update-rc.d homeassistant.sh defaults
# sudo update-rc.d homeassistant.sh enable
#
# You should now be able to start HA by running
# sudo /etc/init.d/homeassistant.sh start

### BEGIN INIT INFO
# Provides:          myservice
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Put a short description of the service here
# Description:       Put a long description of the service here
### END INIT INFO

# Change the next 3 lines to suit where you install your script and what you want to call it
DIR=/home/pi/Apps/home-assistant
DAEMON="/home/pi/.pyenv/shims/python3 -m homeassistant"
DAEMON_NAME=homeassistant

# Add any command line options for your daemon here
DAEMON_OPTS=""

# This next line determines what user the script runs as.
# Root generally not recommended but necessary if you are using the Raspberry Pi GPIO from Python.
DAEMON_USER=pi

# The process ID of the script when it runs is stored here:
PIDFILE=/var/run/$DAEMON_NAME.pid

. /lib/lsb/init-functions

do_start () {
    log_daemon_msg "Starting system $DAEMON_NAME daemon"
    start-stop-daemon --start --background --chdir $DIR --pidfile $PIDFILE --make-pidfile --user $DAEMON_USER --chuid $DAEMON_USER --startas $DAEMON -- $DAEMON_OPTS
    log_end_msg $?
}
do_stop () {
    log_daemon_msg "Stopping system $DAEMON_NAME daemon"
    start-stop-daemon --stop --pidfile $PIDFILE --retry 10
    log_end_msg $?
}

case "$1" in

    start|stop)
        do_${1}
        ;;

    restart|reload|force-reload)
        do_stop
        do_start
        ;;

    status)
        status_of_proc "$DAEMON_NAME" "$DAEMON" && exit 0 || exit $?
        ;;
    *)
        echo "Usage: /etc/init.d/$DAEMON_NAME {start|stop|restart|status}"
        exit 1
        ;;

esac
exit 0
