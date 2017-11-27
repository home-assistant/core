from qqbot import _bot as bot
from homeassistant.helpers.entity import Entity
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import threading
import os

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
    o = Qqsensor()
    add_devices([o])
    thread1 = QQ(config['qq'])
    thread1.start()


class Qqsensor(Entity):
    """Representation of a Qqsensor."""
    def __init__(self):
        """Initialize the sensor."""
        self._state = ' '
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
        with open(path, 'r') as fs:
            ms = fs.read()
        self._state = ms


class QQ(threading.Thread):
        def __init__(self, qq):
            threading.Thread.__init__(self)
            self.thread_stop = False
            self.qq = qq

        def run(self):
            bot.Login(['-u', str(self.qq)])
            bot.Run()

        def stop(self):
            self.thread_stop = True 
