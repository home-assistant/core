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

REQUIREMENTS = ["mychevy==0.1"]

DOMAIN = 'mychevy'

MYCHEVY_SUCCESS = "Success"
MYCHEVY_ERROR = "Error"
MYCHEVY_UNKNOWN = "Unknown"

NOTIFICATION_ID = 'mychevy_website_notification'
NOTIFICATION_TITLE = 'MyChevy website status'

_LOGGER = getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)
ERROR_SLEEP_TIME = 5*60

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


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
        self.add_devices = None
        self.sensors = []
        # This is a status sensor for the connection itself
        self.status = MyChevyStatus(self)

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

    def register_add_devices(self, add_devices):
        """Register add_devices method.

        This creates the initial status sensor, and makes it possible
        for the hub to spin up devices as it has appropriate
        information for them.

        """
        self.add_devices = add_devices
        add_devices([self.status], True)

    def _create_sensors(self):
        """Create the sensors for the car.

        This is not done during initialization because the sensors
        have no value at initialization time.

        """
        self.sensors = [
            EVRange(self),
            EVMileage(self),
            EVCharge(self),
            EVPlugged(self),
            EVCharging(self),
            EVChargeMode(self)
        ]
        add = self.add_devices
        add(self.sensors, True)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update sensors from mychevy website.

        This is a synchronous polling call.
        """
        self.car = self._client.data()
        self.status.success()
        if self.add_devices and not self.sensors:
            self._create_sensors()

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
                time.sleep(ERROR_SLEEP_TIME)


class EVSensor(Entity):
    """Base EVSensor class.

    The only real difference between sensors is which units and what
    attribute from the car object they are returning. All logic can be
    built with just setting subclass attributes.

    """

    _icon = None
    _unit = "miles"
    _name = "EV Sensor"
    _attr = None

    def __init__(self, connection):
        """Initialize sensor with car connection."""
        self._conn = connection
        self.hass = connection.hass
        self.car = connection.car
        self.entity_id = ENTITY_ID_FORMAT.format(
            '{}_{}'.format(DOMAIN, self.__class__.__name__))

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"units": self._unit}

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        if self.car is not None:
            return getattr(self.car, self._attr, None)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the state is expressed in."""
        return self._unit

    @property
    def should_poll(self):
        """Return the polling state."""
        return False


class EVCharge(EVSensor):
    """EVCharge Sensor.

    The charge percentage of the EV battery. It is an integer from 0 -
    100.

    """

    _name = "EV Charge"
    _unit = "percent"
    _attr = "percent"


class EVMileage(EVSensor):
    """EVMileage Sensor.

    The total odometer mileage on the car.
    """

    _name = "EV Mileage"
    _unit = "miles"
    _attr = "mileage"


class EVRange(EVSensor):
    """EV Range.

    The estimated average range of the car. This is going to depend on
    both charge percentage as well as recent driving conditions (for
    instance very cold temperatures drive down the range quite a bit).

    """

    _name = "EST Range"
    _unit = "miles"
    _attr = "range"


class EVPlugged(EVSensor):
    """EV Plugged in.

    Is the EV Plugged in. Returns True or False. This does not
    indicate whether or not it's currently charging.

    """

    _name = "EV Plugged In"
    _unit = None
    _attr = "plugged_in"


class EVCharging(EVSensor):
    """A string representing the charging state."""

    _name = "EV Charging"
    _unit = None
    _attr = "charging"


class EVChargeMode(EVSensor):
    """A string representing the charging mode."""

    _name = "EV Charge Mode"
    _unit = None
    _attr = "charge_mode"


class MyChevyStatus(Entity):
    """A string representing the charge mode."""

    _name = "MyChevy Status"
    _icon = None

    def __init__(self, connection):
        """Initialize sensor with car connection."""
        self._state = MYCHEVY_UNKNOWN
        self._last_update = dt.now()
        self._conn = connection

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"last_update": self._last_update}

    def success(self):
        """Update state, trigger updates."""
        if self._state != MYCHEVY_SUCCESS:
            _LOGGER.info("Successfully connected to mychevy website")
            self._state = MYCHEVY_SUCCESS
        self.schedule_update_ha_state()

    def error(self):
        """Update state, trigger updates."""
        if self._state != MYCHEVY_ERROR:
            self.hass.components.persistent_notification.create(
                "Error:<br/>Connection to mychevy website failed. "
                "This probably means the mychevy to OnStar link is down.",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
            self._state = MYCHEVY_ERROR
        self.schedule_update_ha_state()

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False
