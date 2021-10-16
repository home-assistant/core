"""Platform for the opengarage.io cover component."""
import logging

import voluptuous as vol

from homeassistant import config_entries
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
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_DISTANCE_SENSOR,
    ATTR_DOOR_STATE,
    ATTR_SIGNAL_STRENGTH,
    CONF_DEVICE_KEY,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

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
    _LOGGER.warning(
        "Open Garage YAML configuration is deprecated, "
        "it has been imported into the UI automatically and can be safely removed"
    )
    devices = config.get(CONF_COVERS)
    for device_config in devices.values():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=device_config,
            )
        )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the OpenGarage covers."""
    async_add_entities(
        [OpenGarageCover(hass.data[DOMAIN][entry.entry_id], entry.unique_id)], True
    )


class OpenGarageCover(CoverEntity):
    """Representation of a OpenGarage cover."""

    _attr_device_class = DEVICE_CLASS_GARAGE
    _attr_supported_features = SUPPORT_OPEN | SUPPORT_CLOSE

    def __init__(self, open_garage, device_id):
        """Initialize the cover."""
        self._open_garage = open_garage
        self._state = None
        self._state_before_move = None
        self._extra_state_attributes = {}
        self._attr_unique_id = self._device_id = device_id

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

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self.name,
            "manufacturer": "Open Garage",
        }
        return device_info
