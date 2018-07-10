#!/data/data/pl.sviete.dom/files/usr/bin/sh

set -e -u

SCRIPTNAME=led
show_usage() {
    echo "Usage: $SCRIPTNAME brightness/function"
    echo "Set the led brightness between 0 and 255"
    echo "or trigger the function like heartbeat"
    exit 0
}

if [ $# != 1 ]; then
    show_usage
fi

if [ $1 -eq "0" ]; then
    echo "set the red"
    echo $1 > /sys/class/leds/led-sys/brightness
elif [ $1 -eq "255" ]; then
    echo "set the blue"
    echo $1 > /sys/class/leds/led-sys/brightness
else
    echo "trigger the function"
    echo $1 > /sys/class/leds/led-sys/trigger
fi

# rc-feedback nand-disk timer oneshot heartbeat backlight emmc sd sdio breathe scpi scpistop disturb rfkill0 rfkill3