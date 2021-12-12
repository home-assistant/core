"""Entity representing a Sonos battery level."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SONOS_CREATE_AUDIO_FORMAT_SENSOR, SONOS_CREATE_BATTERY
from .entity import SonosEntity
from .speaker import SonosSpeaker


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    @callback
    def _async_create_audio_format_entity(
        speaker: SonosSpeaker, audio_format: str
    ) -> None:
        entity = SonosAudioInputFormatSensorEntity(speaker, audio_format)
        async_add_entities([entity])

    @callback
    def _async_create_battery_sensor(speaker: SonosSpeaker) -> None:
        entity = SonosBatteryEntity(speaker)
        async_add_entities([entity])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SONOS_CREATE_AUDIO_FORMAT_SENSOR, _async_create_audio_format_entity
        )
    )
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SONOS_CREATE_BATTERY, _async_create_battery_sensor
        )
    )


class SonosBatteryEntity(SonosEntity, SensorEntity):
    """Representation of a Sonos Battery entity."""

    _attr_device_class = DEVICE_CLASS_BATTERY
    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, speaker: SonosSpeaker) -> None:
        """Initialize the battery sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{self.soco.uid}-battery"
        self._attr_name = f"{self.speaker.zone_name} Battery"

    async def _async_poll(self) -> None:
        """Poll the device for the current state."""
        await self.speaker.async_poll_battery()

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.speaker.battery_info.get("Level")

    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self.speaker.available and self.speaker.power_source


class SonosAudioInputFormatSensorEntity(SonosEntity, SensorEntity):
    """Representation of a Sonos audio import format sensor entity."""

    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC
    _attr_icon = "mdi:import"
    _attr_should_poll = True

    def __init__(self, speaker: SonosSpeaker, audio_format: str) -> None:
        """Initialize the audio input format sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{self.soco.uid}-audio-format"
        self._attr_name = f"{self.speaker.zone_name} Audio Input Format"
        self._attr_native_value = audio_format

    def update(self) -> None:
        """Poll the device for the current state."""
        self._attr_native_value = self.soco.soundbar_audio_input_format

    async def _async_poll(self) -> None:
        """Provide a stub for required ABC method."""
