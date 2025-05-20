"""Update platform for ESPHome."""

from __future__ import annotations

import asyncio
from typing import Any

from aioesphomeapi import (
    DeviceInfo as ESPHomeDeviceInfo,
    EntityInfo,
    UpdateCommand,
    UpdateInfo,
    UpdateState,
)

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.enum import try_parse_enum

from .const import DOMAIN
from .coordinator import ESPHomeDashboardCoordinator
from .dashboard import async_get_dashboard
from .entity import (
    EsphomeEntity,
    async_esphome_state_property,
    convert_api_error_ha_error,
    esphome_state_property,
    platform_async_setup_entry,
)
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

PARALLEL_UPDATES = 0

KEY_UPDATE_LOCK = "esphome_update_lock"

NO_FEATURES = UpdateEntityFeature(0)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPHome update based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=UpdateInfo,
        entity_type=ESPHomeUpdateEntity,
        state_type=UpdateState,
    )

    if (dashboard := async_get_dashboard(hass)) is None:
        return
    entry_data = entry.runtime_data
    assert entry_data.device_info is not None
    device_name = entry_data.device_info.name
    unsubs: list[CALLBACK_TYPE] = []

    @callback
    def _async_setup_update_entity() -> None:
        """Set up the update entity."""
        assert dashboard is not None
        # Keep listening until device is available
        if not entry_data.available or not dashboard.last_update_success:
            return

        # Do not add Dashboard Entity if this device is not known to the ESPHome dashboard.
        if dashboard.data is None or dashboard.data.get(device_name) is None:
            return

        for unsub in unsubs:
            unsub()
        unsubs.clear()

        async_add_entities([ESPHomeDashboardUpdateEntity(entry_data, dashboard)])

    if (
        entry_data.available
        and dashboard.last_update_success
        and dashboard.data is not None
        and dashboard.data.get(device_name)
    ):
        _async_setup_update_entity()
        return

    unsubs.extend(
        [
            entry_data.async_subscribe_device_updated(_async_setup_update_entity),
            dashboard.async_add_listener(_async_setup_update_entity),
        ]
    )


class ESPHomeDashboardUpdateEntity(
    CoordinatorEntity[ESPHomeDashboardCoordinator], UpdateEntity
):
    """Defines an ESPHome update entity."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_title = "ESPHome"
    _attr_release_url = "https://esphome.io/changelog/"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, entry_data: RuntimeEntryData, coordinator: ESPHomeDashboardCoordinator
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
        self._install_lock = asyncio.Lock()
        self._available_future: asyncio.Future[None] | None = None
        self._update_attrs()

    @callback
    def _update_attrs(self) -> None:
        """Update the supported features."""
        coordinator = self.coordinator
        device_info = self._device_info
        # Install support can change at run time
        if coordinator.last_update_success and coordinator.supports_update:
            self._attr_supported_features = UpdateEntityFeature.INSTALL
        else:
            self._attr_supported_features = NO_FEATURES
        self._attr_installed_version = device_info.esphome_version
        device = coordinator.data.get(device_info.name)
        assert device is not None
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
        if (
            self._entry_data.available
            and self._available_future
            and not self._available_future.done()
        ):
            self._available_future.set_result(None)
            self._available_future = None
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

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity about to be removed from Home Assistant."""
        if self._available_future and not self._available_future.done():
            self._available_future.cancel()
            self._available_future = None

    async def _async_wait_available(self) -> None:
        """Wait until the device is available."""
        # If the device has deep sleep, we need to wait for it to wake up
        # and connect to the network to be able to install the update.
        if self._entry_data.available:
            return
        self._available_future = self.hass.loop.create_future()
        try:
            await self._available_future
        finally:
            self._available_future = None

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if self._install_lock.locked():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ota_in_progress",
                translation_placeholders={
                    "configuration": self._device_info.name,
                },
            )

        # Ensure only one OTA per device at a time
        async with self._install_lock:
            # Ensure only one compile at a time for ALL devices
            async with self.hass.data.setdefault(KEY_UPDATE_LOCK, asyncio.Lock()):
                coordinator = self.coordinator
                api = coordinator.api
                device = coordinator.data.get(self._device_info.name)
                assert device is not None
                configuration = device["configuration"]
                if not await api.compile(configuration):
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="error_compiling",
                        translation_placeholders={
                            "configuration": configuration,
                        },
                    )

            # If the device uses deep sleep, there's a small chance it goes
            # to sleep right after the dashboard connects but before the OTA
            # starts. In that case, the update won't go through, so we try
            # again to catch it on its next wakeup.
            attempts = 2 if self._device_info.has_deep_sleep else 1
            try:
                for attempt in range(1, attempts + 1):
                    await self._async_wait_available()
                    if await api.upload(configuration, "OTA"):
                        break
                    if attempt == attempts:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="error_uploading",
                            translation_placeholders={
                                "configuration": configuration,
                            },
                        )
            finally:
                await self.coordinator.async_request_refresh()


class ESPHomeUpdateEntity(EsphomeEntity[UpdateInfo, UpdateState], UpdateEntity):
    """A update implementation for esphome."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        self._attr_device_class = try_parse_enum(
            UpdateDeviceClass, static_info.device_class
        )

    @property
    @esphome_state_property
    def installed_version(self) -> str:
        """Return the installed version."""
        return self._state.current_version

    @property
    @esphome_state_property
    def in_progress(self) -> bool:
        """Return if the update is in progress."""
        return self._state.in_progress

    @property
    @esphome_state_property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        return self._state.latest_version

    @async_esphome_state_property
    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        if self._state.release_summary:
            return self._state.release_summary
        return None

    @property
    @esphome_state_property
    def release_url(self) -> str:
        """Return the release URL."""
        return self._state.release_url

    @property
    @esphome_state_property
    def title(self) -> str:
        """Return the title of the update."""
        return self._state.title

    @property
    @esphome_state_property
    def update_percentage(self) -> int | None:
        """Return if the update is in progress."""
        if self._state.has_progress:
            return int(self._state.progress)
        return None

    @convert_api_error_ha_error
    async def async_update(self) -> None:
        """Command device to check for update."""
        if self.available:
            self._client.update_command(key=self._key, command=UpdateCommand.CHECK)

    @convert_api_error_ha_error
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Command device to install update."""
        self._client.update_command(key=self._key, command=UpdateCommand.INSTALL)
