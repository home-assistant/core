"""Entity representing a Sonos power sensor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    BinarySensorEntity,
)
from homeassistant.const import ENTITY_CATEGORY_DIAGNOSTIC
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SONOS_CREATE_BATTERY
from .entity import SonosEntity
from .speaker import SonosSpeaker

ATTR_BATTERY_POWER_SOURCE = "power_source"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    async def _async_create_entity(speaker: SonosSpeaker) -> None:
        _LOGGER.debug("Creating battery binary_sensor on %s", speaker.zone_name)
        entity = SonosPowerEntity(speaker)
        async_add_entities([entity])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_BATTERY, _async_create_entity)
    )


class SonosPowerEntity(SonosEntity, BinarySensorEntity):
    """Representation of a Sonos power entity."""

    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC
    _attr_device_class = DEVICE_CLASS_BATTERY_CHARGING

    def __init__(self, speaker: SonosSpeaker) -> None:
        """Initialize the power entity binary sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{self.soco.uid}-power"
        self._attr_name = f"{self.speaker.zone_name} Power"

    async def _async_poll(self) -> None:
        """Poll the device for the current state."""
        await self.speaker.async_poll_battery()

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.speaker.charging

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            ATTR_BATTERY_POWER_SOURCE: self.speaker.power_source,
        }

    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self.speaker.available and (self.speaker.charging is not None)
