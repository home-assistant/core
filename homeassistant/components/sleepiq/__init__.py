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

BED = "bed"
LEFT = "left"
PRESET_FAVORITE = 0
RIGHT = "right"
SIDE = "side"
SIDES = [LEFT, RIGHT]

SERVICE_SET_SLEEP_NUMBER = "set_sleep_number"
SERVICE_SET_FAVORITE = "set_to_favorite_sleep_number"

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

    def handle_set_number(call):
        bed = call.data.get(BED, "")
        side = call.data.get(SIDE, "")
        new_sleep_number = call.data.get(SLEEP_NUMBER, 0)

        DATA.set_new_sleep_number(bed, side, new_sleep_number)

    def handle_set_favorite(call):
        bed = call.data.get(BED, "")
        side = call.data.get(SIDE, "")

        DATA.set_to_favorite_sleep_number(bed, side)

    hass.services.register(DOMAIN, SERVICE_SET_SLEEP_NUMBER, handle_set_number)
    hass.services.register(DOMAIN, SERVICE_SET_FAVORITE, handle_set_favorite)

    discovery.load_platform(hass, "sensor", DOMAIN, {}, config)
    discovery.load_platform(hass, "binary_sensor", DOMAIN, {}, config)

    return True


class SleepIQData:
    """Get the latest data from SleepIQ."""

    def __init__(self, client):
        """Initialize the data object."""
        self._client = client
        self.beds = {}

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from SleepIQ."""
        self._client.login()
        beds = self._client.beds_with_sleeper_status()

        self.beds = {bed.bed_id: bed for bed in beds}

    def set_new_sleep_number(self, bed_name: str, side: str, sleep_number):
        """Change the sleep number on a side to a new value."""

        # Sanity check: Sleep number has to be between 1-100.
        if 0 < sleep_number <= 100:
            self._set_sleep_number(bed_name, side, int(sleep_number))
        else:
            message = f"Invalid sleep number: {sleep_number}"
            _LOGGER.warning(message)

    def set_to_favorite_sleep_number(self, bed_name: str, side: str):
        """Change a side's sleep number to their 'favorite' setting."""
        self._set_sleep_number(bed_name, side, PRESET_FAVORITE)

    def get_favorite_sleep_number(self, bed_id: int, side: str) -> int:
        """Get a side's 'favorite' number, given a bed ID and a side."""
        favorite_numbers = self._client.get_favsleepnumber(bed_id)
        return getattr(favorite_numbers, side.lower())

    def _set_sleep_number(self, bed_name: str, side: str, new_number: int):
        """Set the sleep number for a side on a bed."""
        bed_name = bed_name.lower()
        side = side.lower()

        if len(side) == 0:
            # No side specified, use both.
            sides_to_set = SIDES
        else:
            # Just use the side we specified.
            sides_to_set = [side]

        for bed_id, bed_obj in self.beds.items():
            # If no bed name is specified, set on all beds.
            # Otherwise, ensure we only set on beds with the correct name.
            if len(bed_name) == 0 or bed_name == bed_obj.name.lower():
                for bed_side in sides_to_set:
                    # Check if we should use the "favorite" preset instead.
                    if new_number == PRESET_FAVORITE:
                        num = self.get_favorite_sleep_number(bed_id, bed_side)
                    else:
                        num = new_number

                    debug_msg = f"Setting {bed_side} of bed {bed_id} to {num}"
                    _LOGGER.debug(debug_msg)

                    # Actually set the Sleep Number.
                    self._client.set_sleepnumber(bed_id, bed_side, num)


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
