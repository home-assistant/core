"""You can use this sensor to link your qq."""
import os
import logging
import threading
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['qqbot==2.3.7']

_LOGGER = logging.getLogger(__name__)

QQ_NUMBER = 'qq_number'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(QQ_NUMBER): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Qqsensors."""
    thread1 = QQ(config[QQ_NUMBER])
    thread1.start()
    object_qq = Qqsensor(hass, QQ_NUMBER, thread1)
    add_devices([object_qq])


class Qqsensor(Entity):
    """Representation of a Qqsensor."""

    def __init__(self, hass, name, thread_qq):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._hass = hass
        self._thread = thread_qq
        self._hass.services.register(self._name, 'stop qq', self.stop)
        self._hass.services.register(self._name, 'run qq', self.run)

    @property
    def should_poll(self):
        """Need polling."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the message of the sensor."""
        return self._state

    def update(self):
        """Get message from file."""
        path = os.path.expanduser('~') + '/.homeassistant'
        path += '/msg.txt'
        file_contain = open(path, 'r')
        if file_contain != '':
            message = file_contain.read()
            self._state = message
            file_contain.close()
            file_chance = open(path, 'w')
            file_chance.write('')
            file_chance.close()
        else:
            self._state = ''

    def stop(self):
        """Stop qq function."""
        self._thread.stop()

    def run(self):
        """Start qq function."""
        self._thread.run()


class QQ(threading.Thread):
    """Representation of qq threading."""

    def __init__(self, qq_number):
        """Initialize threading."""
        threading.Thread.__init__(self)
        self.thread_state = False
        self._qq = qq_number

    def run(self):
        """Run threading."""
        from qqbot import _bot as bot
        if self.thread_state is False:
            self.thread_state = True
            bot.Login(['-u', str(self._qq)])
            bot.Run()

    def stop(self):
        """Stop threading although it could not use."""
        if self.thread_state is True:
            os.system('qq stop')
            self.thread_state = False
