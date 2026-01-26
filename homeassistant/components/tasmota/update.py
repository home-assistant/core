"""Update entity for Tasmota."""

import re

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TasmotaLatestReleaseUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tasmota update entities."""
    coordinator = TasmotaLatestReleaseUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    devices = device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    )
    async_add_entities(TasmotaUpdateEntity(coordinator, device) for device in devices)


class TasmotaUpdateEntity(UpdateEntity):
    """Representation of a Tasmota update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_name = "Firmware"
    _attr_title = "Tasmota firmware"
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: TasmotaLatestReleaseUpdateCoordinator,
        device_entry: DeviceEntry,
    ) -> None:
        """Initialize the Tasmota update entity."""
        self.coordinator = coordinator
        self.device_entry = device_entry
        self._attr_unique_id = f"{device_entry.id}_update"

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        return self.device_entry.sw_version  # type:ignore[union-attr]

    @property
    def latest_version(self) -> str:
        """Return the latest version."""
        return self.coordinator.data.tag_name.removeprefix("v")

    @property
    def release_url(self) -> str:
        """Return the release URL."""
        return self.coordinator.data.html_url

    @property
    def release_summary(self) -> str:
        """Return the release summary."""
        return self.coordinator.data.name

    def release_notes(self) -> str | None:
        """Return the release notes."""
        if not self.coordinator.data.body:
            return None
        return re.sub(
            r"^<picture>.*?</picture>", "", self.coordinator.data.body, flags=re.DOTALL
        )
