"""Support for Freedompro cover."""
import json

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    DEVICE_CLASS_WINDOW,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN
from .utils import putState


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro cover."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    devices = [
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if (
            device["type"] == "windowCovering"
            or device["type"] == "gate"
            or device["type"] == "garageDoor"
            or device["type"] == "door"
            or device["type"] == "window"
        )
    ]

    async_add_entities(devices, False)


class Device(CoordinatorEntity, CoverEntity):
    """Representation of an Freedompro cover."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro cover."""
        super().__init__(coordinator)
        self._hass = hass
        self._api_key = api_key
        self._name = device["name"]
        self._uid = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._position = 0

    @property
    def name(self):
        """Return the name of the Freedompro cover."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this cover."""
        return self._uid

    @property
    def supported_features(self):
        """Supported features for lock."""
        support = SUPPORT_SET_POSITION
        return support

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        if self._position == 0:
            return True
        else:
            return False

    @property
    def current_cover_position(self):
        """Return the status of the current_cover_position."""
        device = next(
            (device for device in self.coordinator.data if device["uid"] == self._uid),
            None,
        )
        if device is not None:
            if "state" in device:
                state = device["state"]
                if "position" in state:
                    self._position = state["position"]
        return self._position

    @property
    def device_class(self):
        """Define class to type of cover."""
        if self._type == "windowCoverig":
            return DEVICE_CLASS_BLIND
        if self._type == "window":
            return DEVICE_CLASS_WINDOW
        if self._type == "gate":
            return DEVICE_CLASS_GATE
        if self._type == "garageDoor":
            return DEVICE_CLASS_GARAGE
        if self._type == "door":
            return DEVICE_CLASS_DOOR
        return DEVICE_CLASS_BLIND

    async def async_set_cover_position(self, **kwargs):
        """Async function to set position to cover."""
        payload = {}
        if ATTR_POSITION in kwargs:
            self._position = kwargs[ATTR_POSITION]
            payload["position"] = self._position
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()
