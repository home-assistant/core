"""Support for Freedompro lock."""
import json

from pyfreedompro import put_state

from homeassistant.components.lock import LockEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro lock."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "lock"
    )


class Device(CoordinatorEntity, LockEntity):
    """Representation of an Freedompro lock."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro lock."""
        super().__init__(coordinator)
        self._hass = hass
        self._session = aiohttp_client.async_get_clientsession(self._hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._attr_device_info = {
            "name": self.name,
            "identifiers": {
                (DOMAIN, self.unique_id),
            },
            "model": self._type,
            "manufacturer": "Freedompro",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["uid"] == self.unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            if "lock" in state:
                if state["lock"] == 1:
                    self._attr_is_locked = True
                else:
                    self._attr_is_locked = False
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_lock(self, **kwargs):
        """Async function to lock the lock."""
        payload = {"lock": 1}
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        """Async function to unlock the lock."""
        payload = {"lock": 0}
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
