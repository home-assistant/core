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
    def _async_create_audio_format_entity(speaker: SonosSpeaker) -> None:
        entity = SonosAudioInputFormatSensorEntity(speaker)
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

    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self.soco.uid}-battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.speaker.zone_name} Battery"

    @property
    def device_class(self) -> str:
        """Return the entity's device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def native_unit_of_measurement(self) -> str:
        """Get the unit of measurement."""
        return PERCENTAGE

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

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self.soco.uid}-audio-format"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.speaker.zone_name} Audio Input Format"

    @property
    def native_value(self) -> str:
        """Return the current state of the text sensor."""
        return self.speaker.soundbar_audio_input_format

    def update(self) -> None:
        """Poll the device for the current state."""
        self.speaker.soundbar_audio_input_format = self.soco.soundbar_audio_input_format

    async def _async_poll(self) -> None:
        """Provide a stub for required ABC method."""
