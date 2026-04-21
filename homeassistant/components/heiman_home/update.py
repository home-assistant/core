"""Update platform for Heiman integration."""

from __future__ import annotations

import logging

from heimanconnect import HeimanDevice

from homeassistant import config_entries
from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Heiman update entities based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Track existing entities to avoid duplicates
    existing_entities: set[str] = set()

    def _create_update_entities_for_devices() -> None:
        """Create update entities for all devices and add new ones."""
        devices = coordinator.get_all_devices()
        new_update_entities = []

        for device in devices:
            unique_id = f"{device.device_id}_firmware_update"
            if unique_id not in existing_entities:
                new_update_entities.append(
                    HeimanUpdateEntity(
                        coordinator=coordinator,
                        device=device,
                    )
                )
                existing_entities.add(unique_id)

        if new_update_entities:
            async_add_entities(new_update_entities)

    # Initial setup
    _create_update_entities_for_devices()

    # Listen for coordinator updates to add new devices dynamically
    entry.async_on_unload(
        coordinator.async_add_listener(_create_update_entities_for_devices)
    )


class HeimanUpdateEntity(CoordinatorEntity[HeimanDataUpdateCoordinator], UpdateEntity):
    """Representation of a Heiman update entity."""

    _attr_has_entity_name = True
    # Note: INSTALL and SPECIFIC_VERSION not supported until API supports firmware updates

    def __init__(
        self,
        coordinator: HeimanDataUpdateCoordinator,
        device: HeimanDevice,
    ) -> None:
        """Initialize the update entity.

        Args:
            coordinator: Data coordinator
            device: Heiman device
        """
        super().__init__(coordinator)
        self._device = device

        # Generate unique ID
        self._attr_unique_id = f"{device.device_id}_firmware_update"

        # Set name
        self._attr_name = "Firmware Info"

        # Extract firmware version - use multiple strategies
        sw_version = self._extract_firmware_version(device)

        # Get device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer=device.manufacturer,
            model=device.model or device.product_id,
            sw_version=sw_version,
            hw_version=device.hardware_version,
        )

        # Initialize version attributes
        self._attr_installed_version = sw_version
        self._attr_latest_version = sw_version  # Default to current version
        self._attr_release_summary = None
        self._attr_release_url = None
        self._attr_title = "Heiman Firmware"
        self._attr_in_progress = False
        self._attr_update_percentage = None
        self._attr_auto_update = False

    def _extract_firmware_version(self, device: HeimanDevice) -> str | None:
        """Extract firmware version from device using multiple strategies.

        Args:
            device: Heiman device

        Returns:
            Firmware version string or None
        """
        sw_version = None

        # Strategy 1: Get directly from device.firmware_version attribute
        if hasattr(device, "firmware_version") and device.firmware_version:
            return device.firmware_version

        # Strategy 2: Get from raw_data.firmwareInfo.version
        if hasattr(device, "raw_data") and device.raw_data:
            firmware_info = device.raw_data.get("firmwareInfo", {})
            if isinstance(firmware_info, dict) and firmware_info.get("version"):
                return firmware_info.get("version")

        # Strategy 3: Get from firmware_info.version
        if hasattr(device, "firmware_info") and device.firmware_info:
            if isinstance(device.firmware_info, dict) and device.firmware_info.get(
                "version"
            ):
                return device.firmware_info.get("version")

        # No firmware version found
        return sw_version

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return False

        return device.online is True

    @property
    def installed_version(self) -> str | None:
        """Return the current installed firmware version."""
        # Return cached version first
        if self._attr_installed_version:
            return self._attr_installed_version

        # Fallback to dynamic fetch
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return None

        return self._extract_firmware_version(device)

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version.

        For now, we don't have a way to check for new firmware versions via API.
        This should be implemented when the API supports firmware update checks.
        """
        # Return cached latest version first
        if self._attr_latest_version:
            return self._attr_latest_version

        # Fallback to installed version (indicates no update available)
        return self.installed_version

    def _update_from_cache(self) -> bool:
        """Update entity state from coordinator cache (synchronous).

        Returns True if state was updated from cache, False if cache miss.
        """
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return False

        # Get installed version
        installed_version = self._extract_firmware_version(device)
        if installed_version:
            # Only update if there's no better version
            if (
                not self._attr_installed_version
                or self._attr_installed_version == "unknown"
            ):
                self._attr_installed_version = installed_version

        # TODO: Populate latest version when the API supports firmware update checks.

        # If no latest version, use installed version
        if installed_version and not self._attr_latest_version:
            self._attr_latest_version = installed_version

        return True

    @property
    def release_summary(self) -> str | None:
        """Return summary of the latest release."""
        # pylint: disable=fixme
        # TODO: Implement when API supports firmware update information
        return None

    @property
    def in_progress(self) -> bool:
        """Return whether an update is currently in progress."""
        # Check if there's a property indicating update status
        device = self.coordinator.get_device(self._device.device_id)
        if device:
            update_prop = device.properties.get("firmware_update_status")
            if update_prop and update_prop.value:
                return str(update_prop.value).lower() in [
                    "updating",
                    "downloading",
                    "installing",
                ]
        return False

    async def async_update(self) -> None:
        """Update the entity state from coordinator cache (polling).

        This is called during polling by Home Assistant.
        Note: HA automatically calls async_write_ha_state() after async_update().
        """
        self._update_from_cache()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).

        This is called when the coordinator has new data (e.g., from MQTT).
        Updates entity state immediately without waiting for next poll.
        """
        if self._update_from_cache():
            # Write the new state to Home Assistant immediately
            self.async_write_ha_state()
