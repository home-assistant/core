"""The lookin integration light platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, TYPE_TO_PLATFORM
from .entity import LookinPowerPushRemoteEntity
from .models import LookinData

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light platform for lookin from a config entry."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for remote in lookin_data.devices:
        if TYPE_TO_PLATFORM.get(remote["Type"]) != Platform.LIGHT:
            continue
        uuid = remote["UUID"]
        coordinator = lookin_data.device_coordinators[uuid]
        device = coordinator.data
        entities.append(
            LookinLightEntity(
                coordinator=coordinator,
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
            )
        )

    async_add_entities(entities)


class LookinLightEntity(LookinPowerPushRemoteEntity, LightEntity):
    """A lookin IR controlled light."""

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_send_command(self._power_on_command)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_send_command(self._power_off_command)
        self._attr_is_on = False
        self.async_write_ha_state()

    def _update_from_status(self, status: str) -> None:
        """Update media property from status.

        1000
        0 - 0/1 on/off
        """
        if len(status) != 4:
            return
        state = status[0]

        self._attr_is_on = state == "1"
