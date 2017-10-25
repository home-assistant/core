"""
Support for interacting with USB Missile Launchers.
Tested with those manufactured by Dream Cheeky.

For more details about this platform, please refer to the documentation at
@TODO

USAGE:
(Place below code in configuration.yaml)
media_player:
    platform: missile_launcher

"""
import sys
import subprocess
import time
import platform
import argparse
import usb.core
import usb.util
import logging
from homeassistant.components.media_player import (MediaPlayerDevice, SUPPORT_SELECT_SOURCE, PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)


# Protocol command bytes
DOWN    = 0x01
UP      = 0x02
LEFT    = 0x04
RIGHT   = 0x08
FIRE    = 0x10
STOP    = 0x20
DEVICE = None
DEVICE_TYPE = None
REQUIREMENTS = []
DOMAIN = 'missile_launcher'
ICON = 'mdi:rocket'
DEFAULT_NAME = 'Missile Launcher'
SUPPORT_MISSILE = SUPPORT_SELECT_SOURCE

# Set Up At Custom Component
def setup_platform(hass, config, add_devices, discovery_info=None):
    name = config.get('name', DEFAULT_NAME)
    # Initialize Device
    add_devices([IMissileSensor(name)])

# Missile Launcher Device
class IMissileSensor(MediaPlayerDevice):
    """Implementation of a Missile Launcher"""
    def __init__(self, name):
        """Initialize the sensor."""
        self._name = name
        # @TODO: The constants have slash from using telegram. Not sure what would be acceptable format or if there is a Standard to use.
        self._source = '/none'
        self._source_list = ['/none', '/right', '/left', '/up', '/down', '/fire']
        # Setup USB
        self.setup_usb()
        # Lastly Do An Update
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_MISSILE
        
    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list
    
    @property
    def media_image_url(self):
        """Return the image URL of current playing media."""
        # @TODO: for the image, I use Motion and place the image in home assistant www folder. Would this be acceptable solution?
        # MAKE SURE THIS FILE HAS WRITE ACCESS
        subprocess.Popen(['fswebcam', '/home/homeassistant/.homeassistant/www/missile_launcher.jpg'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return 'http://127.0.0.1:8123/local/missile_launcher.jpg?1=1&t=%s' % (time.time())
    
    @property
    def state(self):
        """Return the date of the next event."""
        return '/none'

    def select_source(self, source):
        """Set the input source."""
        # @TODO: offer custom time in configuration for x and y movement duration.
        self.run_command(source, 1000)
        
    def update(self):
        """Get the latest update and set the state."""
        self._source = "/none"

    def setup_usb(_self):
        # Tested only with the Cheeky Dream Thunder
        # and original USB Launcher
        # Make Sure USB Has Access by all users
        # https://unix.stackexchange.com/questions/44308/understanding-udev-rules-and-permissions-in-libusb
        global DEVICE 
        global DEVICE_TYPE

        DEVICE = usb.core.find(idVendor=0x2123, idProduct=0x1010)

        if DEVICE is None:
            DEVICE = usb.core.find(idVendor=0x0a81, idProduct=0x0701)
            if DEVICE is None:
                print('Missile device not found')
            else:
                DEVICE_TYPE = "Original"
        else:
            DEVICE_TYPE = "Thunder"
        print(DEVICE_TYPE)
        
        # On Linux we need to detach usb HID first
        try:
            DEVICE.detach_kernel_driver(0)
        except:
            pass # already unregistered    

    def send_cmd(_self, cmd):
        if "Thunder" == DEVICE_TYPE:
            DEVICE.ctrl_transfer(0x21, 0x09, 0, 0, [0x02, cmd, 0x00,0x00,0x00,0x00,0x00,0x00])
        elif "Original" == DEVICE_TYPE:
            DEVICE.ctrl_transfer(0x21, 0x09, 0x0200, 0, [cmd])

    def send_move(_self, cmd, duration_ms):
        _self.send_cmd(cmd)
        time.sleep(duration_ms / 1000.0)
        _self.send_cmd(STOP)

    def run_command(_self, command, value):
        command = command.lower()
        if command == "/right":
            _self.send_move(RIGHT, value)
        elif command == "/left":
            _self.send_move(LEFT, value)
        elif command == "/up":
            _self.send_move(UP, value)
        elif command == "/down":
            _self.send_move(DOWN, value)
        elif command == "/fire" or command == "/shoot":
            if value < 1 or value > 4:
                value = 1
            # Stabilize prior to the shot, then allow for reload time after.
            time.sleep(0.5)
            for i in range(value):
                _self.send_cmd(FIRE)
                time.sleep(4.5)
