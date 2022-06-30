"""Entity representing a Sonos battery level."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    SONOS_CREATE_AUDIO_FORMAT_SENSOR,
    SONOS_CREATE_BATTERY,
    SONOS_CREATE_FAVORITES_SENSOR,
    SONOS_FAVORITES_UPDATED,
    SOURCE_TV,
)
from .entity import SonosEntity, SonosPollingEntity
from .favorites import SonosFavorites
from .helpers import soco_error
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonos from a config entry."""

    @callback
    def _async_create_audio_format_entity(
        speaker: SonosSpeaker, audio_format: str
    ) -> None:
        _LOGGER.debug("Creating audio input format sensor on %s", speaker.zone_name)
        entity = SonosAudioInputFormatSensorEntity(speaker, audio_format)
        async_add_entities([entity])

    @callback
    def _async_create_battery_sensor(speaker: SonosSpeaker) -> None:
        _LOGGER.debug("Creating battery level sensor on %s", speaker.zone_name)
        entity = SonosBatteryEntity(speaker)
        async_add_entities([entity])

    @callback
    def _async_create_favorites_sensor(favorites: SonosFavorites) -> None:
        _LOGGER.debug(
            "Creating favorites sensor (%s items) for household %s",
            favorites.count,
            favorites.household_id,
        )
        entity = SonosFavoritesEntity(favorites)
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

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SONOS_CREATE_FAVORITES_SENSOR, _async_create_favorites_sensor
        )
    )


class SonosBatteryEntity(SonosEntity, SensorEntity):
    """Representation of a Sonos Battery entity."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, speaker: SonosSpeaker) -> None:
        """Initialize the battery sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{self.soco.uid}-battery"
        self._attr_name = f"{self.speaker.zone_name} Battery"

    async def _async_fallback_poll(self) -> None:
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


class SonosAudioInputFormatSensorEntity(SonosPollingEntity, SensorEntity):
    """Representation of a Sonos audio import format sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:import"
    _attr_should_poll = True

    def __init__(self, speaker: SonosSpeaker, audio_format: str) -> None:
        """Initialize the audio input format sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{self.soco.uid}-audio-format"
        self._attr_name = f"{self.speaker.zone_name} Audio Input Format"
        self._attr_native_value = audio_format

    def poll_state(self) -> None:
        """Poll the state if TV source is active and state has settled."""
        if self.speaker.media.source_name != SOURCE_TV and self.state == "No input":
            return
        self._poll_state()

    @soco_error()
    def _poll_state(self) -> None:
        """Poll the device for the current state."""
        self._attr_native_value = self.soco.soundbar_audio_input_format

    async def _async_fallback_poll(self) -> None:
        """Provide a stub for required ABC method."""


class SonosFavoritesEntity(SensorEntity):
    """Representation of a Sonos favorites info entity."""

    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:star"
    _attr_name = "Sonos Favorites"
    _attr_native_unit_of_measurement = "items"
    _attr_should_poll = False

    def __init__(self, favorites: SonosFavorites) -> None:
        """Initialize the favorites sensor."""
        self.favorites = favorites
        self._attr_unique_id = f"{favorites.household_id}-favorites"

    async def async_added_to_hass(self) -> None:
        """Handle common setup when added to hass."""
        await self._async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_FAVORITES_UPDATED}-{self.favorites.household_id}",
                self._async_update_state,
            )
        )

    async def _async_update_state(self) -> None:
        self._attr_native_value = self.favorites.count
        self._attr_extra_state_attributes = {
            "items": {fav.item_id: fav.title for fav in self.favorites}
        }
        self.async_write_ha_state()
