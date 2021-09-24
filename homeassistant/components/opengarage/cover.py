"""Platform for the opengarage.io cover component."""
import logging

import opengarage
import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.const import (
    CONF_COVERS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE_SENSOR = "distance_sensor"
ATTR_DOOR_STATE = "door_state"
ATTR_SIGNAL_STRENGTH = "wifi_signal"

CONF_DEVICE_KEY = "device_key"

DEFAULT_NAME = "OpenGarage"
DEFAULT_PORT = 80

STATES_MAP = {0: STATE_CLOSED, 1: STATE_OPEN}

COVER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_KEY): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA)}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the OpenGarage covers."""
    covers = []
    devices = config.get(CONF_COVERS)

    for device_config in devices.values():
        opengarage_url = (
            f"{'https' if device_config[CONF_SSL] else 'http'}://"
            f"{device_config.get(CONF_HOST)}:{device_config.get(CONF_PORT)}"
        )

        open_garage = opengarage.OpenGarage(
            opengarage_url,
            device_config[CONF_DEVICE_KEY],
            device_config[CONF_VERIFY_SSL],
            async_get_clientsession(hass),
        )
        status = await open_garage.update_state()
        covers.append(
            OpenGarageCover(
                device_config.get(CONF_NAME), open_garage, format_mac(status["mac"])
            )
        )

    async_add_entities(covers, True)


class OpenGarageCover(CoverEntity):
    """Representation of a OpenGarage cover."""

    _attr_device_class = DEVICE_CLASS_GARAGE
    _attr_supported_features = SUPPORT_OPEN | SUPPORT_CLOSE

    def __init__(self, name, open_garage, device_id):
        """Initialize the cover."""
        self._attr_name = name
        self._open_garage = open_garage
        self._state = None
        self._state_before_move = None
        self._extra_state_attributes = {}
        self._attr_unique_id = device_id

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return self._extra_state_attributes

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._state is None:
            return None
        return self._state == STATE_CLOSED

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        if self._state is None:
            return None
        return self._state == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        if self._state is None:
            return None
        return self._state == STATE_OPENING

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        if self._state in [STATE_CLOSED, STATE_CLOSING]:
            return
        self._state_before_move = self._state
        self._state = STATE_CLOSING
        await self._push_button()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        if self._state in [STATE_OPEN, STATE_OPENING]:
            return
        self._state_before_move = self._state
        self._state = STATE_OPENING
        await self._push_button()

    async def async_update(self):
        """Get updated status from API."""
        status = await self._open_garage.update_state()
        if status is None:
            _LOGGER.error("Unable to connect to OpenGarage device")
            self._attr_available = False
            return

        if self.name is None and status["name"] is not None:
            self._attr_name = status["name"]
        state = STATES_MAP.get(status.get("door"))
        if self._state_before_move is not None:
            if self._state_before_move != state:
                self._state = state
                self._state_before_move = None
        else:
            self._state = state

        _LOGGER.debug("%s status: %s", self.name, self._state)
        if status.get("rssi") is not None:
            self._extra_state_attributes[ATTR_SIGNAL_STRENGTH] = status.get("rssi")
        if status.get("dist") is not None:
            self._extra_state_attributes[ATTR_DISTANCE_SENSOR] = status.get("dist")
        if self._state is not None:
            self._extra_state_attributes[ATTR_DOOR_STATE] = self._state

        self._attr_available = True

    async def _push_button(self):
        """Send commands to API."""
        result = await self._open_garage.push_button()
        if result is None:
            _LOGGER.error("Unable to connect to OpenGarage device")
        if result == 1:
            return

        if result == 2:
            _LOGGER.error("Unable to control %s: Device key is incorrect", self.name)
        elif result > 2:
            _LOGGER.error("Unable to control %s: Error code %s", self.name, result)

        self._state = self._state_before_move
        self._state_before_move = None
