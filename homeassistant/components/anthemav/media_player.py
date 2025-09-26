"""Support for Anthem Network Receivers and Processors."""

from __future__ import annotations

import logging

from anthemav.protocol import AVR

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnthemavConfigEntry
from .const import ANTHEMAV_UPDATE_SIGNAL, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)
VOLUME_STEP = 0.01


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AnthemavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    name = config_entry.title
    mac_address = config_entry.data[CONF_MAC]
    model = config_entry.data[CONF_MODEL]

    avr = config_entry.runtime_data

    _LOGGER.debug("Connection data dump: %s", avr.dump_conndata)

    async_add_entities(
        AnthemAVR(
            avr.protocol, name, mac_address, model, zone_number, config_entry.entry_id
        )
        for zone_number in avr.protocol.zones
    )


class AnthemAVR(MediaPlayerEntity):
    """Entity reading values from Anthem AVR protocol."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_volume_step = VOLUME_STEP

    def __init__(
        self,
        avr: AVR,
        name: str,
        mac_address: str,
        model: str,
        zone_number: int,
        entry_id: str,
    ) -> None:
        """Initialize entity with transport."""
        super().__init__()
        self.avr = avr
        self._entry_id = entry_id
        self._zone_number = zone_number
        self._zone = avr.zones[zone_number]
        if zone_number > 1:
            unique_id = f"{mac_address}_{zone_number}"
            self._attr_unique_id = unique_id
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, unique_id)},
                name=f"Zone {zone_number}",
                manufacturer=MANUFACTURER,
                model=model,
                via_device=(DOMAIN, mac_address),
            )
        else:
            self._attr_unique_id = mac_address
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, mac_address)},
                name=name,
                manufacturer=MANUFACTURER,
                model=model,
            )
        self.set_states()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{ANTHEMAV_UPDATE_SIGNAL}_{self._entry_id}",
                self.update_states,
            )
        )

    @callback
    def update_states(self) -> None:
        """Update states for the current zone."""
        self.set_states()
        self.async_write_ha_state()

    def set_states(self) -> None:
        """Set all the states from the device to the entity."""
        self._attr_state = (
            MediaPlayerState.ON if self._zone.power else MediaPlayerState.OFF
        )
        self._attr_is_volume_muted = self._zone.mute
        self._attr_volume_level = self._zone.volume_as_percentage
        self._attr_media_title = self._zone.input_name
        self._attr_app_name = self._zone.input_format
        self._attr_source = self._zone.input_name
        self._attr_source_list = self.avr.input_list

    async def async_select_source(self, source: str) -> None:
        """Change AVR to the designated source (by name)."""
        self._zone.input_name = source

    async def async_turn_off(self) -> None:
        """Turn AVR power off."""
        self._zone.power = False

    async def async_turn_on(self) -> None:
        """Turn AVR power on."""
        self._zone.power = True

    async def async_set_volume_level(self, volume: float) -> None:
        """Set AVR volume (0 to 1)."""
        self._zone.volume_as_percentage = volume

    async def async_mute_volume(self, mute: bool) -> None:
        """Engage AVR mute."""
        self._zone.mute = mute
