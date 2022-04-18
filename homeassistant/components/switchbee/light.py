"""Support for SwitchBee light."""

import logging

import switchbee

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

MAX_BRIGHTNESS = 255

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Freedompro light."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, coordinator.data[device], coordinator)
        for device in coordinator.data
        if coordinator.data[device]["type"] == switchbee.TYPE_DIMMER
    )


class Device(CoordinatorEntity, LightEntity):
    """Representation of an Freedompro light."""

    def __init__(self, hass, device, coordinator):
        """Initialize the Freedompro light."""
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
            model="Dimmer",
            name=self.name,
        )
        self._attr_is_on = False
        self._attr_brightness = 0
        self._attr_supported_features = SUPPORT_BRIGHTNESS

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        state = self.coordinator.data[self._device_id][switchbee.ATTR_STATE]
        if isinstance(state, str):
            if state == switchbee.STATE_OFF:
                self._attr_is_on = False
                self._attr_brightness = 0
            else:
                self._attr_is_on = True
                self._attr_brightness = 100

        elif isinstance(state, int):
            if state > 0:
                self._attr_is_on = True
                self._attr_brightness = int((state * MAX_BRIGHTNESS) / 100)

        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        """Async function to set on to light."""
        if ATTR_BRIGHTNESS in kwargs:
            state = int((kwargs[ATTR_BRIGHTNESS] * 100) / MAX_BRIGHTNESS)
        else:
            state = 100

        result = await self.coordinator.api.set_state(self._device_id, state)
        if (
            result[switchbee.ATTR_STATUS] != switchbee.STATUS_OK
            or result[switchbee.ATTR_DATA] != state
        ):
            _LOGGER.error(
                "Failed to set %s state %s, status=%s, state=%s",
                self._attr_name,
                state,
                result[switchbee.ATTR_STATUS],
                result[switchbee.ATTR_DATA],
            )

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Set the light state using the SwitchBee API."""
        result = await self.coordinator.api.set_state(
            self._device_id, switchbee.STATE_OFF
        )
        if (
            result[switchbee.ATTR_STATUS] != switchbee.STATUS_OK
            or result[switchbee.ATTR_DATA] != switchbee.STATE_OFF
        ):
            _LOGGER.error(
                "Failed to set %s state OFF, status=%s, state=%s",
                self._attr_name,
                result[switchbee.ATTR_STATUS],
                result[switchbee.ATTR_DATA],
            )

        await self.coordinator.async_request_refresh()
