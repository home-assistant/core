"""Breeze switch of the Renson ventilation unit."""

from __future__ import annotations

import logging
from typing import Any

from renson_endura_delta.field_enum import CURRENT_LEVEL_FIELD, DataType
from renson_endura_delta.renson import Level, RensonVentilation

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RensonCoordinator
from .const import DOMAIN
from .entity import RensonEntity

_LOGGER = logging.getLogger(__name__)


class RensonBreezeSwitch(RensonEntity, SwitchEntity):
    """Provide the breeze switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_has_entity_name = True
    _attr_translation_key = "breeze"

    def __init__(
        self,
        api: RensonVentilation,
        coordinator: RensonCoordinator,
    ) -> None:
        """Initialize class."""
        super().__init__("breeze", api, coordinator)

        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        _LOGGER.debug("Enable Breeze")

        await self.hass.async_add_executor_job(self.api.set_manual_level, Level.BREEZE)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        _LOGGER.debug("Disable Breeze")

        await self.hass.async_add_executor_job(self.api.set_manual_level, Level.OFF)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        level = self.api.parse_value(
            self.api.get_field_value(self.coordinator.data, CURRENT_LEVEL_FIELD.name),
            DataType.LEVEL,
        )

        self._attr_is_on = level == Level.BREEZE.value

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Call the Renson integration to setup."""

    api: RensonVentilation = hass.data[DOMAIN][config_entry.entry_id].api
    coordinator: RensonCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    async_add_entities([RensonBreezeSwitch(api, coordinator)])
