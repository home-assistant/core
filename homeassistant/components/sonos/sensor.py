"""Entity representing a Sonos battery level."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    SONOS_CREATE_AUDIO_FORMAT_SENSOR,
    SONOS_CREATE_BATTERY,
    SONOS_CREATE_FAVORITES_SENSOR,
    SONOS_FAVORITES_UPDATED,
    SOURCE_TV,
)
from .entity import SonosEntity, SonosPollingEntity
from .favorites import SonosFavorites
from .helpers import SonosConfigEntry, soco_error
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)

SONOS_POWER_SOURCE_BATTERY = "BATTERY"
SONOS_POWER_SOURCE_CHARGING_RING = "SONOS_CHARGING_RING"
SONOS_POWER_SOURCE_USB = "USB_POWER"

HA_POWER_SOURCE_BATTERY = "battery"
HA_POWER_SOURCE_CHARGING_BASE = "charging_base"
HA_POWER_SOURCE_USB = "usb"

power_source_map = {
    SONOS_POWER_SOURCE_BATTERY: HA_POWER_SOURCE_BATTERY,
    SONOS_POWER_SOURCE_CHARGING_RING: HA_POWER_SOURCE_CHARGING_BASE,
    SONOS_POWER_SOURCE_USB: HA_POWER_SOURCE_USB,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SonosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonos from a config entry."""

    @callback
    def _async_create_audio_format_entity(
        speaker: SonosSpeaker, audio_format: str
    ) -> None:
        _LOGGER.debug("Creating audio input format sensor on %s", speaker.zone_name)
        entity = SonosAudioInputFormatSensorEntity(speaker, config_entry, audio_format)
        async_add_entities([entity])

    @callback
    def _async_create_battery_sensor(speaker: SonosSpeaker) -> None:
        _LOGGER.debug(
            "Creating battery level and power source sensor on %s", speaker.zone_name
        )
        async_add_entities(
            [
                SonosBatteryEntity(speaker, config_entry),
                SonosPowerSourceEntity(speaker, config_entry),
            ]
        )

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

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the battery sensor."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-battery"

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
        return self.speaker.available and self.speaker.power_source is not None


class SonosPowerSourceEntity(SonosEntity, SensorEntity):
    """Representation of a Sonos Power Source entity."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_options = [
        HA_POWER_SOURCE_BATTERY,
        HA_POWER_SOURCE_CHARGING_BASE,
        HA_POWER_SOURCE_USB,
    ]
    _attr_translation_key = "power_source"

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the power source sensor."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-power_source"

    async def _async_fallback_poll(self) -> None:
        """Poll the device for the current state."""
        await self.speaker.async_poll_battery()

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not (power_source := self.speaker.power_source):
            return None
        if not (value := power_source_map.get(power_source)):
            _LOGGER.warning(
                "Unknown power source '%s' for speaker %s",
                power_source,
                self.speaker.zone_name,
            )
            return None
        return value

    @property
    def available(self) -> bool:
        """Return whether this entity is available."""
        return self.speaker.available and self.speaker.power_source is not None


class SonosAudioInputFormatSensorEntity(SonosPollingEntity, SensorEntity):
    """Representation of a Sonos audio import format sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "audio_input_format"
    _attr_should_poll = True

    def __init__(
        self, speaker: SonosSpeaker, config_entry: SonosConfigEntry, audio_format: str
    ) -> None:
        """Initialize the audio input format sensor."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-audio-format"
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
    _attr_name = "Sonos favorites"
    _attr_translation_key = "favorites"
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
