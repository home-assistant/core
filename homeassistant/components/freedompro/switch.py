"""Support for Freedompro switch."""
import json

from pyfreedompro import put_state

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro switch."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "switch" or device["type"] == "outlet"
    )


class Device(CoordinatorEntity, SwitchEntity):
    """Representation of an Freedompro switch."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro switch."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._attr_device_info = {
            "name": self.name,
            "identifiers": {
                (DOMAIN, self.unique_id),
            },
            "model": device["type"],
            "manufacturer": "Freedompro",
        }
        self._attr_is_on = False

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
            if "on" in state:
                self._attr_is_on = state["on"]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        """Async function to set on to switch."""
        payload = {"on": True}
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Async function to set off to switch."""
        payload = {"on": False}
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
