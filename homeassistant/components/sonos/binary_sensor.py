"""Entity representing a Sonos power sensor."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import SonosConfigEntry
from .const import SONOS_CREATE_BATTERY, SONOS_CREATE_MIC_SENSOR
from .entity import SonosEntity
from .helpers import soco_error
from .speaker import SonosSpeaker

ATTR_BATTERY_POWER_SOURCE = "power_source"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonos from a config entry."""

    @callback
    def _async_create_battery_entity(speaker: SonosSpeaker) -> None:
        _LOGGER.debug("Creating battery binary_sensor on %s", speaker.zone_name)
        entity = SonosPowerEntity(speaker, config_entry)
        async_add_entities([entity])

    @callback
    def _async_create_mic_entity(speaker: SonosSpeaker) -> None:
        _LOGGER.debug("Creating microphone binary_sensor on %s", speaker.zone_name)
        async_add_entities([SonosMicrophoneSensorEntity(speaker, config_entry)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SONOS_CREATE_BATTERY, _async_create_battery_entity
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SONOS_CREATE_MIC_SENSOR, _async_create_mic_entity
        )
    )


class SonosPowerEntity(SonosEntity, BinarySensorEntity):
    """Representation of a Sonos power entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the power entity binary sensor."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-power"

    async def _async_fallback_poll(self) -> None:
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


class SonosMicrophoneSensorEntity(SonosEntity, BinarySensorEntity):
    """Representation of a Sonos microphone sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "microphone"

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the microphone binary sensor entity."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-microphone"

    async def _async_fallback_poll(self) -> None:
        """Handle polling when subscription fails."""
        await self.hass.async_add_executor_job(self.poll_state)

    @soco_error()
    def poll_state(self) -> None:
        """Poll the current state of the microphone."""
        self.speaker.mic_enabled = self.soco.mic_enabled

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.speaker.mic_enabled
