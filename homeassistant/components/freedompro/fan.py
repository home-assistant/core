"""Support for Freedompro fan."""
import json

from homeassistant.components.fan import FanEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN
from .utils import putState


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro fan."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    devices = [
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "fan"
    ]

    async_add_entities(devices, False)


class Device(CoordinatorEntity, FanEntity):
    """Representation of an Freedompro cover."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro fan."""
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
        """Return the name of the Freedompro fan."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this fan."""
        return self._uid

    @property
    def supported_features(self):
        """Supported features for lock."""
        support = 0
        return support

    @property
    def is_on(self):
        """Return the status of the fan."""
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
        """Async function to set on to fan."""
        self._on = True
        payload = {"on": self._on}
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Async function to set off to fan."""
        self._on = False
        payload = {"on": self._on}
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()
