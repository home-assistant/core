"""Support for DROP switches."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_TYPE,
    DEV_FILTER,
    DEV_HUB,
    DEV_PROTECTION_VALVE,
    DEV_SOFTENER,
    DOMAIN as DROP_DOMAIN,
)
from .coordinator import DROP_DeviceDataUpdateCoordinator
from .entity import DROP_Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DROP switches from config entry."""
    _LOGGER.debug(
        "Set up switch for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )

    entities = []
    if config_entry.data[CONF_DEVICE_TYPE] == DEV_HUB:
        entities.extend(
            [
                DROP_WaterStateSwitch(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
                DROP_BypassStateSwitch(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )
    elif (
        config_entry.data[CONF_DEVICE_TYPE] == DEV_SOFTENER
        or config_entry.data[CONF_DEVICE_TYPE] == DEV_FILTER
    ):
        entities.extend(
            [
                DROP_BypassStateSwitch(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )
    elif config_entry.data[CONF_DEVICE_TYPE] == DEV_PROTECTION_VALVE:
        entities.extend(
            [
                DROP_WaterStateSwitch(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )
    async_add_entities(entities)


class DROP_WaterStateSwitch(DROP_Entity, SwitchEntity):
    """Water ON/OFF switch class for the DROP system."""

    _attr_translation_key = "water"

    def __init__(self, device: DROP_DeviceDataUpdateCoordinator) -> None:
        """Initialize the DROP water switch."""
        super().__init__("water", device)
        self._attr_is_on = device.last_known_water_state == "ON"

    @property
    def icon(self) -> str:
        """Return the icon to use for the water state (valves)."""
        if self.is_on:
            return "mdi:valve-open"
        return "mdi:valve-closed"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Open the valves."""
        await self._device.set_water_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Close the valves."""
        await self._device.set_water_off()
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def async_update_state(self) -> None:
        """Retrieve the latest valve state and update the state machine."""
        self._attr_is_on = self._device.last_known_water_state == "ON"
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self._device.async_add_listener(self.async_update_state))


class DROP_BypassStateSwitch(DROP_Entity, SwitchEntity):
    """Bypass ON/OFF switch class for the DROP system."""

    _attr_translation_key = "bypass"

    def __init__(self, device: DROP_DeviceDataUpdateCoordinator) -> None:
        """Initialize the DROP bypass switch."""
        super().__init__("bypass", device)
        self._attr_is_on = device.last_known_bypass_state == "ON"

    @property
    def icon(self) -> str:
        """Return the icon to use for the bypass state (valves)."""
        if self.is_on:
            return "mdi:valve-open"
        return "mdi:valve-closed"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Open the valves."""
        await self._device.set_bypass_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Close the valves."""
        await self._device.set_bypass_off()
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def async_update_state(self) -> None:
        """Retrieve the latest valve state and update the state machine."""
        self._attr_is_on = self._device.last_known_bypass_state == "ON"
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self._device.async_add_listener(self.async_update_state))
