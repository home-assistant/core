"""Update entity for Tasmota."""

import re
from typing import override

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import Event, HassJobType, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_device_registry_updated_event
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
            device := device_registry.async_get_device_by_connection(
                (CONNECTION_NETWORK_MAC, mac), config_entry.entry_id
            )
        ):
            added_macs.add(mac)
            entity = TasmotaUpdateEntity(coordinator, device, mac)
            entity.async_on_remove(lambda: added_macs.discard(mac))
            async_add_entities([entity])

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(Platform.UPDATE)] = (
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
    _attr_title = "Tasmota firmware"
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: TasmotaLatestReleaseUpdateCoordinator,
        device_entry: DeviceEntry,
        mac: str,
    ) -> None:
        """Initialize the Tasmota update entity."""
        super().__init__(coordinator=coordinator)
        self._device_id = device_entry.id
        self._attr_installed_version = device_entry.sw_version
        self._attr_device_info = dr.DeviceInfo(connections=device_entry.connections)
        self._attr_unique_id = dr.format_mac(mac)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to device-registry updates for firmware changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_device_registry_updated_event(
                self.hass,
                self._device_id,
                self._handle_device_registry_update,
                job_type=HassJobType.Callback,
            )
        )

    @callback
    def _handle_device_registry_update(
        self, event: Event[dr.EventDeviceRegistryUpdatedData]
    ) -> None:
        """Refresh state when the device's firmware version changes."""
        if (
            event.data["action"] != "update"
            or "sw_version" not in event.data["changes"]
        ):
            return
        if device := dr.async_get(self.hass).async_get(
            self._device_id, include_child_devices=False
        ):
            self._attr_installed_version = device.sw_version
            self.async_write_ha_state()

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
    async def async_release_notes(self) -> str | None:
        """Return full release notes."""
        if not self.coordinator.data or not self.coordinator.data.body:
            return None
        # Remove the picture tag, it uses relative URLs that won't work in the UI
        return re.sub(
            r"^<picture>.*?</picture>", "", self.coordinator.data.body, flags=re.DOTALL
        )
