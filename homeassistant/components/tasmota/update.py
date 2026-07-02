"""Update entity for Tasmota."""

import re
from typing import override

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .coordinator import TasmotaLatestReleaseUpdateCoordinator
from .discovery import TASMOTA_DISCOVERY_DEVICE_DISCOVERED


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tasmota update entities."""
    coordinator = config_entry.runtime_data = TasmotaLatestReleaseUpdateCoordinator(
        hass, config_entry
    )
    await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)

    # Track device IDs we've already created update entities for
    created_device_ids: set[str] = set()

    # Create entities for devices that already exist in the registry
    for device in device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    ):
        created_device_ids.add(device.id)
        async_add_entities([TasmotaUpdateEntity(coordinator, device)])

    @callback
    def async_device_discovered(mac: str) -> None:
        """Create update entity for a newly discovered Tasmota device."""
        device = device_registry.async_get_device(
            connections={(CONNECTION_NETWORK_MAC, mac)}
        )
        if (
            device is None
            or config_entry.entry_id not in device.config_entries
            or device.id in created_device_ids
        ):
            return
        created_device_ids.add(device.id)
        async_add_entities([TasmotaUpdateEntity(coordinator, device)])

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format("update")] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_DEVICE_DISCOVERED,
            async_device_discovered,
        )
    )


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
        self.device_entry = device_entry
        self._attr_device_info = dr.DeviceInfo(connections=device_entry.connections)
        self._attr_unique_id = f"{device_entry.id}_update"

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed version."""
        return self.device_entry.sw_version  # type:ignore[union-attr]

    @property
    @override
    def latest_version(self) -> str:
        """Return the latest version."""
        return self.coordinator.data.tag_name.removeprefix("v")

    @property
    @override
    def release_url(self) -> str:
        """Return the release URL."""
        return self.coordinator.data.html_url

    @property
    @override
    def release_summary(self) -> str:
        """Return the release summary."""
        return self.coordinator.data.name

    @override
    def release_notes(self) -> str | None:
        """Return the release notes."""
        if not self.coordinator.data.body:
            return None
        # Remove the picture tag, it uses relative URLs that won't work in the UI
        return re.sub(
            r"^<picture>.*?</picture>", "", self.coordinator.data.body, flags=re.DOTALL
        )
