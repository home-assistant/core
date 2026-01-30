"""Support for ESPHome Dashboard update entities."""

from __future__ import annotations

import logging
from typing import Any

from esphome_dashboard_api import ConfiguredDevice

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ESPHomeDashboardConfigEntry
from .const import DOMAIN
from .coordinator import ESPHomeDashboardCoordinator

_LOGGER = logging.getLogger(__name__)

# All entities share a DataUpdateCoordinator, so no parallel updates needed
PARALLEL_UPDATES = 0


def _find_esphome_device_mac(hass: HomeAssistant, device_name: str) -> str | None:
    """Find MAC address for an ESPHome device by name in device registry."""
    dev_reg = dr.async_get(hass)

    # Search for device by name (case-insensitive comparison)
    for device in dev_reg.devices.values():
        if device.name and device.name.lower() == device_name.lower():
            # Check if this device has a MAC connection (from ESPHome integration)
            for conn_type, conn_id in device.connections:
                if conn_type == CONNECTION_NETWORK_MAC:
                    return conn_id
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeDashboardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPHome Dashboard update entities."""
    coordinator: ESPHomeDashboardCoordinator = entry.runtime_data.coordinator

    # Track which devices we've already created entities for
    known_devices: set[str] = set()

    @callback
    def async_add_update_entities() -> None:
        """Add update entities for devices."""
        entities: list[ESPHomeDashboardUpdateEntity] = []

        for device_name, device_data in coordinator.data.items():
            if device_name not in known_devices:
                known_devices.add(device_name)
                # Try to find MAC address for existing ESPHome device
                mac_address = _find_esphome_device_mac(hass, device_name)
                entities.append(
                    ESPHomeDashboardUpdateEntity(
                        coordinator, device_name, device_data, mac_address
                    )
                )

        if entities:
            async_add_entities(entities)

    # Add entities on initial setup
    async_add_update_entities()

    # Add entities when new devices are discovered and register cleanup
    entry.async_on_unload(coordinator.async_add_listener(async_add_update_entities))


class ESPHomeDashboardUpdateEntity(
    CoordinatorEntity[ESPHomeDashboardCoordinator], UpdateEntity
):
    """Representation of an ESPHome device firmware update status."""

    _attr_has_entity_name = True
    _attr_name = "Firmware"

    @property
    def entity_picture(self) -> str:
        """Return the entity picture to use in the frontend.

        Use ESPHome brand icon since this integration is part of the ESPHome brand.
        """
        return "https://brands.home-assistant.io/_/esphome/icon.png"

    def __init__(
        self,
        coordinator: ESPHomeDashboardCoordinator,
        device_name: str,
        device_data: ConfiguredDevice,
        mac_address: str | None,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)

        # config_entry is always set for this coordinator
        assert coordinator.config_entry is not None
        entry_id = coordinator.config_entry.entry_id

        self._device_name = device_name
        self._attr_unique_id = f"{entry_id}_{device_name}"

        # Store configuration filename and address for OTA updates
        self._configuration = device_data.get("configuration", f"{device_name}.yaml")
        self._address = device_data.get("address")

        # Build configuration URL from dashboard URL
        dashboard_url = coordinator.config_entry.data[CONF_URL]
        configuration_url = f"{dashboard_url.rstrip('/')}/"

        # Link to existing ESPHome device using MAC address connection
        # This ensures the update entity appears on the same device as the ESPHome integration
        if mac_address:
            # Use only connections to link to existing ESPHome device
            self._attr_device_info = DeviceInfo(
                connections={(CONNECTION_NETWORK_MAC, mac_address)},
            )
        else:
            # Fallback: create standalone device if no MAC address available
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_{device_name}")},
                name=device_name,
                manufacturer="ESPHome",
                configuration_url=configuration_url,
            )

        self._update_attrs(device_data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._device_name in self.coordinator.data:
            device_data = self.coordinator.data[self._device_name]
            self._update_attrs(device_data)
        else:
            # Device was removed from dashboard
            self._attr_available = False

        self.async_write_ha_state()

    def _update_attrs(self, device_data: ConfiguredDevice) -> None:
        """Update entity attributes from device data."""
        self._attr_available = True

        # Get version information from ESPHome Dashboard API:
        # - deployed_version: firmware version currently running on the device
        # - current_version: version available in the YAML configuration
        deployed_version = device_data.get("deployed_version")
        available_version = device_data.get("current_version")

        self._attr_installed_version = deployed_version
        self._attr_latest_version = available_version or deployed_version

        # Store address for OTA updates
        self._address = device_data.get("address")

        # Enable install feature if device has an address for OTA
        if self._address:
            self._attr_supported_features = UpdateEntityFeature.INSTALL
        else:
            self._attr_supported_features = UpdateEntityFeature(0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device_name in self.coordinator.data

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update.

        Compiles the configuration and uploads it to the device via OTA.
        """
        if not self._address:
            raise HomeAssistantError(
                f"Cannot install update: no address available for {self._device_name}"
            )

        _LOGGER.info(
            "Starting OTA update for %s (%s) to %s",
            self._device_name,
            self._address,
            self._configuration,
        )

        # Use the API to compile and upload
        api = self.coordinator.api

        # First compile the configuration
        compile_success = await api.compile(self._configuration)
        if not compile_success:
            raise HomeAssistantError(f"Failed to compile {self._configuration}")

        _LOGGER.debug("Compilation successful, starting upload to %s", self._address)

        # Upload to the device via OTA
        upload_success = await api.upload(
            self._configuration,
            self._address,
        )
        if not upload_success:
            raise HomeAssistantError(
                f"Failed to upload to {self._device_name} at {self._address}"
            )

        _LOGGER.info(
            "Successfully updated %s to latest version",
            self._device_name,
        )

        # Refresh coordinator data to get updated version info
        await self.coordinator.async_request_refresh()
