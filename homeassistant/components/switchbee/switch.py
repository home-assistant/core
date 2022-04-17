"""Support for SwitchBee switch."""
import json

import switchbee

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Freedompro switch."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, coordinator.data[device], coordinator)
        for device in coordinator.data
        if coordinator.data[device]["type"]
        in [switchbee.TYPE_SWITCH, switchbee.TYPE_OUTLET]
    )


class Device(CoordinatorEntity, SwitchEntity):
    """Representation of an Freedompro switch."""

    def __init__(self, hass, device, coordinator):
        """Initialize the Freedompro switch."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._attr_name = device["name"]
        self._device_id = device[switchbee.ATTR_ID]
        self._attr_unique_id = device["uid"]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device["uid"]),
            },
            manufacturer="SwitchBee",
            model="Switch",
            name=self.name,
        )
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attr_is_on = (
            self.coordinator.data[self._device_id][switchbee.ATTR_STATE]
            == switchbee.STATE_ON
        )

        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        """Async function to set on to switch."""
        await self.coordinator.api.set_state(self._device_id, switchbee.STATE_ON)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Async function to set off to switch."""
        payload = {"on": False}
        payload = json.dumps(payload)
        await self.coordinator.api.set_state(self._device_id, switchbee.STATE_OFF)
        await self.coordinator.async_request_refresh()
