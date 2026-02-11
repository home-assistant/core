"""Support for Magic Home switches."""

from __future__ import annotations

from typing import Any

from flux_led import DeviceType
from flux_led.aio import AIOWifiLedBulb
from flux_led.const import MODE_MUSIC

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_REMOTE_ACCESS_ENABLED,
    CONF_REMOTE_ACCESS_HOST,
    CONF_REMOTE_ACCESS_PORT,
)
from .coordinator import FluxLedConfigEntry, FluxLedUpdateCoordinator
from .discovery import async_clear_discovery_cache
from .entity import FluxBaseEntity, FluxEntity, FluxOnOffEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FluxLedConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator = entry.runtime_data
    entities: list[FluxSwitch | FluxRemoteAccessSwitch | FluxMusicSwitch] = []
    base_unique_id = entry.unique_id or entry.entry_id

    if coordinator.device.device_type == DeviceType.Switch:
        entities.append(FluxSwitch(coordinator, base_unique_id, None))

    if entry.data.get(CONF_REMOTE_ACCESS_HOST):
        entities.append(FluxRemoteAccessSwitch(coordinator.device, entry))

    if coordinator.device.microphone:
        entities.append(FluxMusicSwitch(coordinator, base_unique_id, "music"))

    async_add_entities(entities)


class FluxSwitch(
    FluxOnOffEntity, CoordinatorEntity[FluxLedUpdateCoordinator], SwitchEntity
):
    """Representation of a Flux switch."""

    _attr_name = None

    async def _async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if not self.is_on:
            await self._device.async_turn_on()


class FluxRemoteAccessSwitch(FluxBaseEntity, SwitchEntity):
    """Representation of a Flux remote access switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "remote_access"

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: FluxLedConfigEntry,
    ) -> None:
        """Initialize the light."""
        super().__init__(device, entry)
        base_unique_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_unique_id}_remote_access"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the remote access on."""
        await self._device.async_enable_remote_access(
            self.entry.data[CONF_REMOTE_ACCESS_HOST],
            self.entry.data[CONF_REMOTE_ACCESS_PORT],
        )
        await self._async_update_entry(True)

    async def _async_update_entry(self, new_state: bool) -> None:
        """Update the entry with the new state on success."""
        async_clear_discovery_cache(self.hass, self._device.ipaddr)
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={**self.entry.data, CONF_REMOTE_ACCESS_ENABLED: new_state},
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the remote access off."""
        await self._device.async_disable_remote_access()
        await self._async_update_entry(False)

    @property
    def is_on(self) -> bool:
        """Return true if remote access is enabled."""
        return bool(self.entry.data[CONF_REMOTE_ACCESS_ENABLED])


class FluxMusicSwitch(FluxEntity, SwitchEntity):
    """Representation of a Flux music switch."""

    _attr_translation_key = "music"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the microphone on."""
        await self._async_ensure_device_on()
        await self._device.async_set_music_mode()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the microphone off."""
        await self._device.async_set_levels(*self._device.rgb, brightness=255)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        """Return true if microphone is is on."""
        return self._device.is_on and self._device.effect == MODE_MUSIC
