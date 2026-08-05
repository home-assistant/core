"""Update entity for Tasmota."""

import re
from typing import override

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .coordinator import TasmotaConfigEntry, TasmotaLatestReleaseUpdateCoordinator
from .discovery import TASMOTA_DISCOVERY_DEVICE_DISCOVERED


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TasmotaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tasmota update entities."""
    coordinator = config_entry.runtime_data

    device_registry = dr.async_get(hass)
    added_macs: set[str] = set()

    @callback
    def async_device_discovered(mac: str) -> None:
        """Create update entity for a newly discovered Tasmota device."""
        if mac not in added_macs and (
            device := device_registry.async_get_device(
                connections={(CONNECTION_NETWORK_MAC, mac)}
            )
        ):
            added_macs.add(mac)
            async_add_entities([TasmotaUpdateEntity(coordinator, device)])

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(Platform.UPDATE)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_DEVICE_DISCOVERED,
            async_device_discovered,
        )
    )

    await coordinator.async_request_refresh()


class TasmotaUpdateEntity(
    CoordinatorEntity[TasmotaLatestReleaseUpdateCoordinator], UpdateEntity
):
    """Representation of a Tasmota update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_title = "Tasmota firmware"
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: TasmotaLatestReleaseUpdateCoordinator,
        device_entry: DeviceEntry,
    ) -> None:
        """Initialize the Tasmota update entity."""
        super().__init__(coordinator=coordinator)
        self._connections = device_entry.connections
        self._attr_device_info = dr.DeviceInfo(connections=self._connections)
        for connection_type, connection_value in self._connections:
            if connection_type == dr.CONNECTION_NETWORK_MAC:
                self._attr_unique_id = connection_value
                break

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed version."""
        if self.hass and (
            device := dr.async_get(self.hass).async_get_device(
                connections=self._connections
            )
        ):
            return device.sw_version
        return None

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest version."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.tag_name.removeprefix("v")

    @property
    @override
    def release_url(self) -> str | None:
        """Return the release URL."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.html_url

    @property
    @override
    def release_summary(self) -> str | None:
        """Return the release summary."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.name

    @override
    def release_notes(self) -> str | None:
        """Return the release notes."""
        if not self.coordinator.data or not self.coordinator.data.body:
            return None
        # Remove the picture tag, it uses relative URLs that won't work in the UI
        return re.sub(
            r"^<picture>.*?</picture>", "", self.coordinator.data.body, flags=re.DOTALL
        )
