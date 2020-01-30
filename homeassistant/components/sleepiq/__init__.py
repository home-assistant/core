"""Support for SleepIQ from SleepNumber."""
from datetime import timedelta
import logging

from sleepyq import Sleepyq
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

DOMAIN = "sleepiq"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

IS_IN_BED = "is_in_bed"
SLEEP_NUMBER = "sleep_number"
SENSOR_TYPES = {SLEEP_NUMBER: "SleepNumber", IS_IN_BED: "Is In Bed"}

LEFT = "left"
RIGHT = "right"
SIDES = [LEFT, RIGHT]

LEFT_NIGHT_STAND = 1
RIGHT_NIGHT_STAND = 2
RIGHT_NIGHT_LIGHT = 3
LEFT_NIGHT_LIGHT = 4

BED_LIGHTS = {
    LEFT_NIGHT_STAND: "Left Night Stand",
    RIGHT_NIGHT_STAND: "Right Night Stand",
    RIGHT_NIGHT_LIGHT: "Right Night Light",
    LEFT_NIGHT_LIGHT: "Left Night Light",
}

SLEEPIQ_COMPONENTS = [
    "binary_sensor",
    "sensor",
    "light",
]

_LOGGER = logging.getLogger(__name__)

DATA = None

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(DOMAIN): vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the SleepIQ component.

    Will automatically load sensor components to support
    devices discovered on the account.

    Will automatically create light components for
    nightstand and under bed lights.
    """
    global DATA

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    client = Sleepyq(username, password)
    try:
        DATA = SleepIQData(client)
        DATA.update()
    except ValueError:
        message = """
            SleepIQ failed to login, double check your username and password"
        """
        _LOGGER.error(message)
        return False

    for component in SLEEPIQ_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class SleepIQData:
    """Get the latest data from SleepIQ."""

    def __init__(self, client):
        """Initialize the data object."""
        self._client = client
        self.beds = {}
        self.lights = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from SleepIQ."""
        self._client.login()
        beds = self._client.beds_with_sleeper_status()

        self.beds = {bed.bed_id: bed for bed in beds}

        for bed in self.beds:
            self.lights = {light: self.get_light(bed, light) for light in BED_LIGHTS}

    def set_light(self, bed_id, light, state):
        """Set a light to a new state."""
        self._client.set_light(bed_id, light, state)

    def get_light(self, bed_id, light):
        """Return current light state."""
        return self._client.get_light(bed_id, light)


class SleepIQSensor(Entity):
    """Implementation of a SleepIQ sensor."""

    def __init__(self, sleepiq_data, bed_id, side):
        """Initialize the sensor."""
        self._bed_id = bed_id
        self._side = side
        self.sleepiq_data = sleepiq_data
        self.side = None
        self.bed = None

        # added by subclass
        self._name = None
        self.type = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "SleepNumber {} {} {}".format(
            self.bed.name, self.side.sleeper.first_name, self._name
        )

    def update(self):
        """Get the latest data from SleepIQ and updates the states."""
        # Call the API for new sleepiq data. Each sensor will re-trigger this
        # same exact call, but that's fine. We cache results for a short period
        # of time to prevent hitting API limits.
        self.sleepiq_data.update()

        self.bed = self.sleepiq_data.beds[self._bed_id]
        self.side = getattr(self.bed, self._side)


class SleepIQLight(Entity):
    """Implementation of a SleepIQ Light."""

    def __init__(self, sleepiq_data, bed_id, light):
        """Initialize the light."""
        self._bed_id = bed_id
        self.sleepiq_data = sleepiq_data
        self._light = light

        self._state = False
        self._name = "SleepNumber {} {}".format(
            self.sleepiq_data.beds[self._bed_id].name, BED_LIGHTS[light]
        )

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    def turn_on(self):
        """Turn on the light."""
        self.sleepiq_data.set_light(self._bed_id, self._light, True)

    def turn_off(self):
        """Turn off the light."""
        self.sleepiq_data.set_light(self._bed_id, self._light, False)

    @property
    def is_on(self):
        """Ask for state of current light."""
        status = self.sleepiq_data.get_light(self._bed_id, self._light)
        return status.data["setting"]

    def update(self):
        """Get the latest light states from SleepIQ."""
        self.sleepiq_data.update()
