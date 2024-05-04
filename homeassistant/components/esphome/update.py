"""Update platform for ESPHome."""

from __future__ import annotations

import asyncio
from typing import Any

from aioesphomeapi import DeviceInfo as ESPHomeDeviceInfo, EntityInfo

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .dashboard import ESPHomeDashboard, async_get_dashboard
from .domain_data import DomainData
from .entry_data import RuntimeEntryData

KEY_UPDATE_LOCK = "esphome_update_lock"

NO_FEATURES = UpdateEntityFeature(0)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESPHome update based on a config entry."""
    if (dashboard := async_get_dashboard(hass)) is None:
        return
    entry_data = DomainData.get(hass).get_entry_data(entry)
    unsubs: list[CALLBACK_TYPE] = []

    @callback
    def _async_setup_update_entity() -> None:
        """Set up the update entity."""
        nonlocal unsubs
        assert dashboard is not None
        # Keep listening until device is available
        if not entry_data.available or not dashboard.last_update_success:
            return

        for unsub in unsubs:
            unsub()
        unsubs.clear()

        async_add_entities([ESPHomeUpdateEntity(entry_data, dashboard)])

    if entry_data.available and dashboard.last_update_success:
        _async_setup_update_entity()
        return

    unsubs = [
        entry_data.async_subscribe_device_updated(_async_setup_update_entity),
        dashboard.async_add_listener(_async_setup_update_entity),
    ]


class ESPHomeUpdateEntity(CoordinatorEntity[ESPHomeDashboard], UpdateEntity):
    """Defines an ESPHome update entity."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_title = "ESPHome"
    _attr_name = "Firmware"
    _attr_release_url = "https://esphome.io/changelog/"

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
        self._update_attrs()

    @callback
    def _update_attrs(self) -> None:
        """Update the supported features."""
        # If the device has deep sleep, we can't assume we can install updates
        # as the ESP will not be connectable (by design).
        coordinator = self.coordinator
        device_info = self._device_info
        # Install support can change at run time
        if (
            coordinator.last_update_success
            and coordinator.supports_update
            and not device_info.has_deep_sleep
        ):
            self._attr_supported_features = UpdateEntityFeature.INSTALL
        else:
            self._attr_supported_features = NO_FEATURES
        self._attr_installed_version = device_info.esphome_version
        device = coordinator.data.get(device_info.name)
        if device is None:
            self._attr_latest_version = None
        else:
            self._attr_latest_version = device["current_version"]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()

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
        return super().available and (
            self._entry_data.available
            or self._entry_data.expected_disconnect
            or self._device_info.has_deep_sleep
        )

    @callback
    def _handle_device_update(
        self, static_info: list[EntityInfo] | None = None
    ) -> None:
        """Handle updated data from the device."""
        self._update_attrs()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()
        entry_data = self._entry_data
        self.async_on_remove(
            entry_data.async_subscribe_static_info_updated(self._handle_device_update)
        )
        self.async_on_remove(
            entry_data.async_subscribe_device_updated(self._handle_device_update)
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        async with self.hass.data.setdefault(KEY_UPDATE_LOCK, asyncio.Lock()):
            coordinator = self.coordinator
            api = coordinator.api
            device = coordinator.data.get(self._device_info.name)
            assert device is not None
            try:
                if not await api.compile(device["configuration"]):
                    raise HomeAssistantError(
                        f"Error compiling {device['configuration']}; "
                        "Try again in ESPHome dashboard for more information."
                    )
                if not await api.upload(device["configuration"], "OTA"):
                    raise HomeAssistantError(
                        f"Error updating {device['configuration']} via OTA; "
                        "Try again in ESPHome dashboard for more information."
                    )
            finally:
                await self.coordinator.async_request_refresh()
