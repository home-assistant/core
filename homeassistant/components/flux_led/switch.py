"""Support for Magic Home switches."""
from __future__ import annotations

from typing import Any

from flux_led import DeviceType
from flux_led.aio import AIOWifiLedBulb

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FluxLedUpdateCoordinator
from .const import (
    CONF_REMOTE_ACCESS_ENABLED,
    CONF_REMOTE_ACCESS_HOST,
    CONF_REMOTE_ACCESS_PORT,
    DOMAIN,
)
from .entity import FluxBaseEntity, FluxOnOffEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[FluxSwitch | FluxRemoteAccessSwitch] = []

    if coordinator.device.device_type == DeviceType.Switch:
        entities.append(
            FluxSwitch(
                coordinator,
                entry.unique_id,
                entry.data[CONF_NAME],
            )
        )

    if entry.data.get(CONF_REMOTE_ACCESS_HOST):
        entities.append(FluxRemoteAccessSwitch(coordinator.device, entry))

    if entities:
        async_add_entities(entities)


class FluxSwitch(FluxOnOffEntity, CoordinatorEntity, SwitchEntity):
    """Representation of a Flux switch."""

    async def _async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if not self.is_on:
            await self._device.async_turn_on()


class FluxRemoteAccessSwitch(FluxBaseEntity, SwitchEntity):
    """Representation of a Flux remote access switch."""

    _attr_should_poll = False

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the light."""
        super().__init__(device, entry)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_name = f"{entry.data[CONF_NAME]} Remote Access"
        if entry.unique_id:
            self._attr_unique_id = f"{entry.unique_id}_remote_access"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the remote access on."""
        await self._device.async_enable_remote_access(
            self.entry.data[CONF_REMOTE_ACCESS_HOST],
            self.entry.data[CONF_REMOTE_ACCESS_PORT],
        )
        # The device will reboot so we must reload
        await self.hass.config_entries.async_reload(self.entry.entry_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the remote access off."""
        await self._device.async_disable_remote_access()
        # The device will reboot so we must reload
        await self.hass.config_entries.async_reload(self.entry.entry_id)

    @property
    def is_on(self) -> bool:
        """Return true if remote access is enabled."""
        return bool(self.entry.data[CONF_REMOTE_ACCESS_ENABLED])
