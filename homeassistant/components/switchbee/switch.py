"""Support for SwitchBee switch."""
import logging

import switchbee

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbee switch."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, coordinator.data[device], coordinator)
        for device in coordinator.data
        if coordinator.data[device]["type"]
        in [switchbee.TYPE_SWITCH, switchbee.TYPE_OUTLET]
    )


class Device(CoordinatorEntity, SwitchEntity):
    """Representation of an Switchbee switch."""

    def __init__(self, hass, device, coordinator):
        """Initialize the Switchbee switch."""
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
            model=device["type"].title(),
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
        result = await self.coordinator.api.set_state(
            self._device_id, switchbee.STATE_ON
        )
        if (
            result[switchbee.ATTR_STATUS] != switchbee.STATUS_OK
            or result[switchbee.ATTR_DATA] != switchbee.STATE_ON
        ):
            _LOGGER.error(
                "Failed to set %s state ON, status=%s, state=%s",
                self._attr_name,
                result[switchbee.ATTR_STATUS],
                result[switchbee.ATTR_DATA],
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Async function to set off to switch."""
        result = await self.coordinator.api.set_state(
            self._device_id, switchbee.STATE_OFF
        )
        if (
            result[switchbee.ATTR_STATUS] != switchbee.STATUS_OK
            or result[switchbee.ATTR_DATA] != switchbee.STATE_OFF
        ):
            _LOGGER.error(
                "Failed to set %s state ON, status=%s, state=%s",
                self._attr_name,
                result[switchbee.ATTR_STATUS],
                result[switchbee.ATTR_DATA],
            )
        await self.coordinator.async_request_refresh()
