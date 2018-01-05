"""
Support for Chevy Bolt EV sensors.

For more details about this platform, please refer to the documentation at
"""

from logging import getLogger
from datetime import datetime as dt
from datetime import timedelta
import time
import threading

import voluptuous as vol

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ["mychevy==0.1.1"]

DOMAIN = 'mychevy'

MYCHEVY_SUCCESS = "Success"
MYCHEVY_ERROR = "Error"

NOTIFICATION_ID = 'mychevy_website_notification'
NOTIFICATION_TITLE = 'MyChevy website status'

_LOGGER = getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)
ERROR_SLEEP_TIME = timedelta(minutes=30)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


class EVSensorConfig(object):
    def __init__(self, name, attr, unit_of_measurement=None, icon=None):
        self.name = name
        self.attr = attr
        self.unit_of_measurement = unit_of_measurement
        self.icon = icon

class EVBinarySensorConfig(object):
    def __init__(self, name, attr, device_class=None):
        self.name = name
        self.attr = attr
        self.device_class = device_class


def setup(hass, base_config):
    """Setup mychevy platform."""
    import mychevy.mychevy as mc

    config = base_config.get(DOMAIN)
    _LOGGER.debug('Received configuration: %s', config)

    email = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = MyChevyHub(mc.MyChevy(email, password), hass)
        hass.data[DOMAIN].start()

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)

    return True


class MyChevyHub(threading.Thread):
    """MyChevy Hub.

    Connecting to the mychevy website is done through a selenium
    webscraping process. That can only run synchronously. In order to
    prevent blocking of other parts of Home Assistant the architecture
    launches a polling loop in a thread.

    When new data is received, sensors are updated, and hass is
    signaled that there are updates. Sensors are not created until the
    first update, which will be 60 - 120 seconds after the platform
    starts.
    """

    def __init__(self, client, hass, **kwags):
        """Initialize MyChevy Hub."""
        super(MyChevyHub, self).__init__()
        self._client = client
        self.hass = hass
        self._car = None
        self.status = None
        self.sensors = []

    @property
    def car(self):
        """An instance of mychevy.mychevy.EVCar."""
        return self._car

    @car.setter
    def car(self, data):
        """Update the EVCar.

        Also update all linked sensors in hass and signal the platform
        there are updates.

        """
        self._car = data
        for sensor in self.sensors:
            sensor.car = data
            sensor.schedule_update_ha_state()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update sensors from mychevy website.

        This is a synchronous polling call that takes a very long time
        (like 2 to 3 minutes long time)

        """
        self.car = self._client.data()
        self.status.success()

    def run(self):
        """Thread run loop."""
        # We add the status device first outside of the loop

        # And then busy wait on threads
        while True:
            try:
                _LOGGER.info("Starting mychevy loop")
                self.update()
                time.sleep(MIN_TIME_BETWEEN_UPDATES.seconds)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Error updating mychevy data. "
                    "This probably means the OnStar link is down again")
                self.status.error()
                time.sleep(ERROR_SLEEP_TIME.seconds)




# class EVCharge(EVSensor):
#     """EVCharge Sensor.

#     The charge percentage of the EV battery. It is an integer from 0 -
#     100.

#     """

#     _name = "EV Charge"
#     _unit = "%"
#     _attr = "percent"

#     @property
#     def icon(self):
#         state = int(self.state / 10)
#         if state == 10:
#             return "mdi:battery"
#         if state >= 1 and state < 10:
#             return "mdi:battery-%d0" % state
#         if state < 1:
#             return "mdi:battery-alert"


# class EVMileage(EVSensor):
#     """EVMileage Sensor.

#     The total odometer mileage on the car.
#     """

#     _name = "EV Mileage"
#     _unit = "miles"
#     _attr = "mileage"
#     _icon = "mdi:speedometer"


# class EVRange(EVSensor):
#     """EV Range.

#     The estimated average range of the car. This is going to depend on
#     both charge percentage as well as recent driving conditions (for
#     instance very cold temperatures drive down the range quite a bit).

#     """

#     _name = "EST Range"
#     _unit = "miles"
#     _attr = "range"
#     _icon = "mdi:speedometer"


# class EVPlugged(EVSensor):
#     """EV Plugged in.

#     Is the EV Plugged in. Returns True or False. This does not
#     indicate whether or not it's currently charging.

#     """

#     _name = "EV Plugged In"
#     _unit = None
#     _attr = "plugged_in"


# class EVCharging(EVSensor):
#     """A string representing the charging state."""

#     _name = "EV Charging"
#     _unit = None
#     _attr = "charging"


# class EVChargeMode(EVSensor):
#     """A string representing the charging mode."""

#     _name = "EV Charge Mode"
#     _unit = None
#     _attr = "charge_mode"
