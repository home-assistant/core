"""Support for ESPHome Dashboard update entities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aioesphomeapi import APIClient, APIConnectionError
from esphome_dashboard_api import ConfiguredDevice
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant.components import zeroconf
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ESPHomeDashboardConfigEntry
from .const import DOMAIN
from .coordinator import ESPHomeDashboardCoordinator

if TYPE_CHECKING:
    from homeassistant.components.esphome import RuntimeEntryData

# ESPHome native API default port (same as esphome.const.DEFAULT_PORT)
DEFAULT_PORT = 6053

_LOGGER = logging.getLogger(__name__)

# ESPHome mDNS service type for port discovery
ESPHOME_SERVICE_TYPE = "_esphomelib._tcp.local."

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


def _find_esphome_entry_data(
    hass: HomeAssistant, device_name: str
) -> RuntimeEntryData | None:
    """Find RuntimeEntryData for an ESPHome device by name.

    Returns the RuntimeEntryData from a loaded ESPHome config entry if the
    device name matches. This allows us to get the actual device version
    instead of relying on the dashboard's potentially stale deployed_version.
    """
    for entry in hass.config_entries.async_entries("esphome"):
        if entry.state != ConfigEntryState.LOADED:
            continue
        entry_data: RuntimeEntryData = entry.runtime_data
        if entry_data.device_info and entry_data.device_info.name == device_name:
            return entry_data
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

        # Version tracking - prefer esphome integration version over dashboard
        self._esphome_entry_data: RuntimeEntryData | None = None
        self._cached_device_version: str | None = None
        self._esphome_unsubscribe: CALLBACK_TYPE | None = None
        self._dashboard_deployed_version: str | None = None

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

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()

        # Try to find esphome integration entry for this device
        self._esphome_entry_data = _find_esphome_entry_data(
            self.hass, self._device_name
        )

        if self._esphome_entry_data:
            _LOGGER.debug(
                "Using version from esphome integration for %s", self._device_name
            )
            # Subscribe to device updates for version changes
            self._esphome_unsubscribe = (
                self._esphome_entry_data.async_subscribe_device_updated(
                    self._handle_esphome_device_update
                )
            )
            # Update state immediately with esphome version
            self.async_write_ha_state()
        elif self._address:
            # Not in esphome integration - query device directly
            self.hass.async_create_task(self._async_fetch_device_version())

    async def _async_discover_device_port(self) -> int | None:
        """Discover device port via mDNS.

        Returns the native API port advertised by the device, or None if not found.
        """
        try:
            aiozc = await zeroconf.async_get_async_instance(self.hass)
            service_name = f"{self._device_name}.{ESPHOME_SERVICE_TYPE}"

            info = AsyncServiceInfo(ESPHOME_SERVICE_TYPE, service_name)
            if await info.async_request(aiozc.zeroconf, timeout=3.0):
                _LOGGER.debug(
                    "Discovered port %s for %s via mDNS", info.port, self._device_name
                )
                return info.port
        except (TimeoutError, OSError, AttributeError):
            # AttributeError can occur if zeroconf is not properly initialized
            _LOGGER.debug("Failed to discover port for %s via mDNS", self._device_name)
        return None

    async def _async_query_device_version(self, address: str) -> str | None:
        """Query device version directly via native API.

        Returns the esphome_version from the device, or None if query fails.
        """
        # Discover port via mDNS, fall back to default
        port = await self._async_discover_device_port()
        if port is None:
            port = DEFAULT_PORT

        _LOGGER.debug(
            "Querying %s directly for version via port %s", self._device_name, port
        )

        client = APIClient(address, port=port, password="")
        try:
            await client.connect(login=False)
            device_info = await client.device_info()
        except APIConnectionError:
            _LOGGER.debug(
                "Direct query failed for %s, using dashboard version", self._device_name
            )
            return None
        else:
            return device_info.esphome_version
        finally:
            await client.disconnect()

    async def _async_fetch_device_version(self) -> None:
        """Fetch device version via direct API query and update state."""
        if not self._address:
            return

        version = await self._async_query_device_version(self._address)
        if version:
            self._cached_device_version = version
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity being removed from Home Assistant."""
        if self._esphome_unsubscribe:
            self._esphome_unsubscribe()
            self._esphome_unsubscribe = None

    @callback
    def _handle_esphome_device_update(self) -> None:
        """Handle device update from esphome integration."""
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Re-check for esphome integration if not already linked
        # (handles case where esphome loads after esphome_dashboard)
        if not self._esphome_entry_data:
            entry_data = _find_esphome_entry_data(self.hass, self._device_name)
            if entry_data:
                _LOGGER.debug(
                    "Found esphome integration for %s on coordinator update",
                    self._device_name,
                )
                self._esphome_entry_data = entry_data
                self._esphome_unsubscribe = entry_data.async_subscribe_device_updated(
                    self._handle_esphome_device_update
                )
                # Clear cached version since esphome has authoritative data
                self._cached_device_version = None

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
        # - deployed_version: firmware version currently running on the device (can be stale)
        # - current_version: version available in the YAML configuration
        self._dashboard_deployed_version = device_data.get("deployed_version")
        available_version = device_data.get("current_version")

        self._attr_latest_version = (
            available_version or self._dashboard_deployed_version
        )

        # Store address for OTA updates
        self._address = device_data.get("address")

        # Enable install feature if device has an address for OTA
        if self._address:
            self._attr_supported_features = UpdateEntityFeature.INSTALL
        else:
            self._attr_supported_features = UpdateEntityFeature(0)

    @property
    def installed_version(self) -> str | None:
        """Return installed version with priority: esphome > cached > dashboard.

        The ESPHome dashboard's deployed_version can be stale or incorrect.
        Prefer the actual version from the device when available.
        """
        # Priority 1: ESPHome integration (authoritative, live updates)
        if self._esphome_entry_data and self._esphome_entry_data.device_info:
            return self._esphome_entry_data.device_info.esphome_version

        # Priority 2: Cached version from direct API query
        if self._cached_device_version:
            return self._cached_device_version

        # Priority 3: Fallback to dashboard's deployed_version
        return self._dashboard_deployed_version

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

        # Clear cached version to force re-query after OTA
        self._cached_device_version = None

        # Refresh coordinator data to get updated version info from dashboard
        await self.coordinator.async_request_refresh()

        # If not using esphome integration, re-query device version
        # (device needs time to reboot after OTA, but we can try immediately)
        if not self._esphome_entry_data and self._address:
            await self._async_fetch_device_version()
