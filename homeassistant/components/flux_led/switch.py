"""Support for Magic Home switches."""
from __future__ import annotations

from typing import Any

from flux_led import DeviceType
from flux_led.aio import AIOWifiLedBulb
from flux_led.const import MODE_MUSIC

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_REMOTE_ACCESS_ENABLED,
    CONF_REMOTE_ACCESS_HOST,
    CONF_REMOTE_ACCESS_PORT,
    DOMAIN,
)
from .coordinator import FluxLedUpdateCoordinator
from .discovery import async_clear_discovery_cache
from .entity import FluxBaseEntity, FluxEntity, FluxOnOffEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[FluxSwitch | FluxRemoteAccessSwitch | FluxMusicSwitch] = []
    base_unique_id = entry.unique_id or entry.entry_id
    name = entry.data.get(CONF_NAME, entry.title)

    if coordinator.device.device_type == DeviceType.Switch:
        entities.append(FluxSwitch(coordinator, base_unique_id, name, None))

    if entry.data.get(CONF_REMOTE_ACCESS_HOST):
        entities.append(FluxRemoteAccessSwitch(coordinator.device, entry))

    if coordinator.device.microphone:
        entities.append(
            FluxMusicSwitch(coordinator, base_unique_id, f"{name} Music", "music")
        )

    async_add_entities(entities)


class FluxSwitch(
    FluxOnOffEntity, CoordinatorEntity[FluxLedUpdateCoordinator], SwitchEntity
):
    """Representation of a Flux switch."""

    async def _async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if not self.is_on:
            await self._device.async_turn_on()


class FluxRemoteAccessSwitch(FluxBaseEntity, SwitchEntity):
    """Representation of a Flux remote access switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the light."""
        super().__init__(device, entry)
        self._attr_name = f"{entry.data.get(CONF_NAME, entry.title)} Remote Access"
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

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        return "mdi:cloud-outline" if self.is_on else "mdi:cloud-off-outline"


class FluxMusicSwitch(FluxEntity, SwitchEntity):
    """Representation of a Flux music switch."""

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

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        return "mdi:microphone" if self.is_on else "mdi:microphone-off"
