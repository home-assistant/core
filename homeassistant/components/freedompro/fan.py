"""Support for Freedompro fan."""
import json

from pyfreedompro import put_state

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro fan."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FreedomproFan(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "fan"
    )


class FreedomproFan(CoordinatorEntity, FanEntity):
    """Representation of an Freedompro fan."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro fan."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._characteristics = device["characteristics"]
        self._attr_device_info = {
            "name": self.name,
            "identifiers": {
                (DOMAIN, self.unique_id),
            },
            "model": device["type"],
            "manufacturer": "Freedompro",
        }
        self._attr_is_on = False
        self._attr_percentage = 0

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._attr_is_on

    @property
    def percentage(self):
        """Return the current speed percentage."""
        return self._attr_percentage

    @property
    def supported_features(self):
        """Flag supported features."""
        if "rotationSpeed" in self._characteristics:
            return SUPPORT_SET_SPEED
        return 0

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
            self._attr_is_on = state["on"]
            if "rotationSpeed" in state:
                self._attr_percentage = state["rotationSpeed"]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(
        self, speed=None, percentage=None, preset_mode=None, **kwargs
    ):
        """Async function to turn on the fan."""
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
        """Async function to turn off the fan."""
        payload = {"on": False}
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int):
        """Set the speed percentage of the fan."""
        rotation_speed = {"rotationSpeed": percentage}
        payload = json.dumps(rotation_speed)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
