"""You can use this sensor to link your qq"""
import os
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import threading

from qqbot import _bot as bot
from homeassistant.helpers.entity import Entity

DOMAIN = 'qq'
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required('qq'): cv.string,
            }),
    },
    extra=vol.ALLOW_EXTRA)

REQUIREMENTS = ['qqbot==2.3.7']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Qqsensors."""
    object_qq = Qqsensor()
    add_devices([object_qq])
    thread1 = QQ(config['qq'])
    thread1.start()


class Qqsensor(Entity):
    """Representation of a Qqsensor."""
    def __init__(self):
        """Initialize the sensor."""
        self._state = 'NULL'
        self._name = DOMAIN
        self._mutex = threading.Lock()

    @property
    def should_poll(self):
        """need polling"""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the message of the sensor."""
        return self._name

    def update(self):
        """get message from file"""
        path = os.path.expanduser('~') + '/.homeassistant'
        path += '/msg.txt'
        with open(path, 'r') as file_contain:
            message = file_contain.read()
        self._state = message


class QQ(threading.Thread):
    """Representation of qq threading."""
    def __init__(self, qq):
        """Initialize threading"""
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.qq = qq

    def run(self):
        """run threading"""
        bot.Login(['-u', str(self.qq)])
        bot.Run()

    def stop(self):
        """stop threading although it could not use."""
        self.thread_stop = True 
