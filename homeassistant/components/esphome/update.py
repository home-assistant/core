"""Update platform for ESPHome."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from aioesphomeapi import DeviceInfo as ESPHomeDeviceInfo, EntityInfo

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .dashboard import ESPHomeDashboard, async_get_dashboard
from .domain_data import DomainData
from .entry_data import RuntimeEntryData

KEY_UPDATE_LOCK = "esphome_update_lock"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESPHome update based on a config entry."""
    dashboard = async_get_dashboard(hass)

    if dashboard is None:
        return

    entry_data = DomainData.get(hass).get_entry_data(entry)
    unsub = None

    async def setup_update_entity() -> None:
        """Set up the update entity."""
        nonlocal unsub

        # Keep listening until device is available
        if not entry_data.available:
            return

        if unsub is not None:
            unsub()  # type: ignore[unreachable]

        assert dashboard is not None
        async_add_entities([ESPHomeUpdateEntity(entry_data, dashboard)])

    if entry_data.available:
        await setup_update_entity()
        return

    signal = f"esphome_{entry_data.entry_id}_on_device_update"
    unsub = async_dispatcher_connect(hass, signal, setup_update_entity)


class ESPHomeUpdateEntity(CoordinatorEntity[ESPHomeDashboard], UpdateEntity):
    """Defines an ESPHome update entity."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_title = "ESPHome"
    _attr_name = "Firmware"

    def __init__(
        self, entry_data: RuntimeEntryData, coordinator: ESPHomeDashboard
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator=coordinator)
        assert entry_data.device_info is not None
        self._entry_data = entry_data
        self._attr_unique_id = entry_data.device_info.mac_address
        self._attr_device_info = DeviceInfo(
            connections={
                (dr.CONNECTION_NETWORK_MAC, entry_data.device_info.mac_address)
            }
        )

        # If the device has deep sleep, we can't assume we can install updates
        # as the ESP will not be connectable (by design).
        if coordinator.supports_update and not self._device_info.has_deep_sleep:
            self._attr_supported_features = UpdateEntityFeature.INSTALL

    @property
    def _device_info(self) -> ESPHomeDeviceInfo:
        """Return the device info."""
        assert self._entry_data.device_info is not None
        return self._entry_data.device_info

    @property
    def available(self) -> bool:
        """Return if update is available.

        During deep sleep the ESP will not be connectable (by design)
        and thus, even when unavailable, we'll show it as available.
        """
        return (
            super().available
            and (self._entry_data.available or self._device_info.has_deep_sleep)
            and self._device_info.name in self.coordinator.data
        )

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        return self._device_info.esphome_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        device = self.coordinator.data.get(self._device_info.name)
        if device is None:
            return None
        return cast(str, device["current_version"])

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return "https://esphome.io/changelog/"

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()

        @callback
        def _static_info_updated(infos: list[EntityInfo]) -> None:
            """Handle static info update."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._entry_data.signal_static_info_updated,
                _static_info_updated,
            )
        )

        @callback
        def _on_device_update() -> None:
            """Handle update of device state, like availability."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._entry_data.signal_device_updated,
                _on_device_update,
            )
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        async with self.hass.data.setdefault(KEY_UPDATE_LOCK, asyncio.Lock()):
            device = self.coordinator.data.get(self._device_info.name)
            assert device is not None
            if not await self.coordinator.api.compile(device["configuration"]):
                logging.getLogger(__name__).error(
                    "Error compiling %s. Try again in ESPHome dashboard for error",
                    device["configuration"],
                )
            if not await self.coordinator.api.upload(device["configuration"], "OTA"):
                logging.getLogger(__name__).error(
                    "Error OTA updating %s. Try again in ESPHome dashboard for error",
                    device["configuration"],
                )
            await self.coordinator.async_request_refresh()
