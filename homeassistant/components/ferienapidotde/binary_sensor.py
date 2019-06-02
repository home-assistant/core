"""Binary sensor to indicate if today is a german vacation day or not."""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ALL_STATE_CODES = [
    "BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL",
    "SN", "ST", "SH", "TH"
]

ATTR_START = 'start'
ATTR_END = 'end'
ATTR_NEXT_START = 'next_start'
ATTR_NEXT_END = 'next_end'
ATTR_VACATION_NAME = 'vacation_name'

CONF_STATE_CODE = 'state_code'

DEFAULT_NAME = 'Vacation Sensor'

# Don't rush the api. Every 12h should suffice.
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=12)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATE_CODE): vol.In(ALL_STATE_CODES),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Setups the ferienapidotde platform."""
    state_code = config.get(CONF_STATE_CODE)
    name = config.get(CONF_NAME)

    import aiohttp.client_exceptions as exc
    try:
        data_object = VacationData(state_code)
        await data_object.async_update()
    except exc.ClientError:
        import traceback
        _LOGGER.warning(traceback.format_exc())
        raise PlatformNotReady()

    async_add_entities([VacationSensor(name, data_object)], True)


class VacationSensor(BinarySensorDevice):
    """Implementation of the vacation sensor."""

    def __init__(self, name, data_object):
        """Initialize the vacation sensor."""
        self._name = name
        self.data_object = data_object
        self._state = None
        self._state_attrs = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of this device."""
        return self._state_attrs

    async def async_update(self):
        """Update the state and state attributes."""
        import ferien
        await self.data_object.async_update()
        vacations = self.data_object.data
        current = ferien.current_vacation(vacs=vacations)
        if current:
            self._state = True
            aligned_end = current.end - timedelta(seconds=1)
            self._state_attrs = {
                ATTR_START: current.start.strftime('%Y-%m-%d'),
                ATTR_END: aligned_end.strftime('%Y-%m-%d'),
                ATTR_VACATION_NAME: current.name
            }
        else:
            self._state = False
            next_vacation = ferien.next_vacation(vacs=vacations)
            if next_vacation:
                aligned_end = next_vacation.end - timedelta(seconds=1)
                self._state_attrs = {
                    ATTR_NEXT_START: next_vacation.start.strftime('%Y-%m-%d'),
                    ATTR_NEXT_END: aligned_end.strftime('%Y-%m-%d'),
                    ATTR_VACATION_NAME: next_vacation.name
                }
            else:
                self._state_attrs = {}


class VacationData:
    """Class for handling data retrieval."""

    def __init__(self, state_code):
        """Initializer."""
        self.state_code = str(state_code)
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update the publicly available data container."""
        import aiohttp.client_exceptions as exc
        try:
            import ferien
            self.data = await ferien.state_vacations_async(self.state_code)
        except exc.ClientError:
            if self.data is None:
                raise
            _LOGGER.error("Failed to update the vacation data."
                          "Re-using an old state")
