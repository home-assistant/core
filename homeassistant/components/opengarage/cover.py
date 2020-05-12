"""Platform for the opengarage.io cover component."""
import logging

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.const import (
    CONF_COVERS,
    CONF_NAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.util import slugify

from .const import ATTR_DISTANCE_SENSOR, ATTR_DOOR_STATE, ATTR_SIGNAL_STRENGTH, DOMAIN

_LOGGER = logging.getLogger(__name__)


STATES_MAP = {0: STATE_CLOSED, 1: STATE_OPEN}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the OpenGarage covers."""
    covers = []
    open_garage = hass.data.get(DOMAIN)
    devices = entry.data[CONF_COVERS]

    for device_config in devices.values():
        covers.append(OpenGarageCover(device_config.get(CONF_NAME), open_garage))

    async_add_entities(covers, True)


class OpenGarageCover(CoverEntity):
    """Representation of a OpenGarage cover."""

    def __init__(self, open_garage, mac):
        """Initialize the cover."""
        self._open_garage = open_garage
        self._name = ""
        self._state = None
        self._state_before_move = None
        self._device_state_attributes = {}
        self._available = True
        self._device_id = slugify(mac)

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._device_state_attributes

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._state is None:
            return None
        return self._state in [STATE_CLOSED, STATE_OPENING]

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
            self._available = False
            return

        if self._name is None and status["name"] is not None:
            self._name = status["name"]
        state = STATES_MAP.get(status.get("door"))
        if self._state_before_move is not None:
            if self._state_before_move != state:
                self._state = state
                self._state_before_move = None
        else:
            self._state = state

        _LOGGER.debug("%s status: %s", self._name, self._state)
        if status.get("rssi") is not None:
            self._device_state_attributes[ATTR_SIGNAL_STRENGTH] = status.get("rssi")
        if status.get("name") is not None:
            self._name = status.get("name")
        if status.get("dist") is not None:
            self._device_state_attributes[ATTR_DISTANCE_SENSOR] = status.get("dist")
        if self._state is not None:
            self._device_state_attributes[ATTR_DOOR_STATE] = self._state

        self._available = True

    async def _push_button(self):
        """Send commands to API."""
        result = await self._open_garage.push_button()
        if result is None:
            _LOGGER.error("Unable to connect to OpenGarage device")
        if result == 1:
            return

        if result == 2:
            _LOGGER.error("Unable to control %s: Device key is incorrect", self._name)
        elif result > 2:
            _LOGGER.error("Unable to control %s: Error code %s", self._name, result)

        self._state = self._state_before_move
        self._state_before_move = None

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_GARAGE

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def device_id(self):
        """Return the ID of the physical device this sensor is part of."""
        return self._device_id

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.device_id}_cover"

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = {
            "name": self.name,
            "manufacturer": "Open Garage",
        }
        if self.model is not None:
            device_info["model"] = self.model
        return device_info
