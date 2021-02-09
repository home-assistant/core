"""Support for Freedompro switch."""
import json
import logging

from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    DEVICE_CLASS_SWITCH,
    SwitchEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN
from .utils import putState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro switch."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    devices = [
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if (device["type"] == "switch" or device["type"] == "outlet")
    ]

    async_add_entities(devices, False)


class Device(CoordinatorEntity, SwitchEntity):
    """Representation of an Freedompro switch."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro switch."""
        super().__init__(coordinator)
        self._hass = hass
        self._api_key = api_key
        self._name = device["name"]
        self._uid = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._on = False

    @property
    def name(self):
        """Return the name of the Freedompro switch."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this switch."""
        return self._uid

    @property
    def supported_features(self):
        """Supported features for lock."""
        support = 0
        return support

    @property
    def device_class(self):
        """Define class to type of switch."""
        if self._type == "switch":
            return DEVICE_CLASS_SWITCH
        if self._type == "outlet":
            return DEVICE_CLASS_OUTLET
        return DEVICE_CLASS_SWITCH

    @property
    def is_on(self):
        """Return the status of the switch."""
        device = next(
            (device for device in self.coordinator.data if device["uid"] == self._uid),
            None,
        )
        if device is not None:
            if "state" in device:
                state = device["state"]
                if "on" in state:
                    self._on = state["on"]
        return self._on

    async def async_turn_on(self, **kwargs):
        """Async function to set on to switch."""
        self._on = True
        payload = {"on": self._on}
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Async function to set off to switch."""
        self._on = False
        payload = {"on": self._on}
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()
