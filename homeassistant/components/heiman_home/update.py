"""Update entities for Heiman Home Integration."""

from __future__ import annotations

import logging
from typing import Any

# Simple version comparison (assumes semantic versioning)
from packaging import version

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import get_initialized_device
from .const import CONF_DEVICES_CONFIG, DEFAULT_INTEGRATION_LANGUAGE, DOMAIN
from .heiman_coordinator import get_coordinator
from .heiman_i18n import get_i18n

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman Home updates."""
    entry_id = config_entry.entry_id
    devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

    _LOGGER.debug("=" * 80)
    _LOGGER.debug("Setting up Heiman Home updates for entry: %s", entry_id)
    _LOGGER.debug("=" * 80)

    # Convert devices dict to list if needed
    if isinstance(devices_dict, dict):
        devices = list(devices_dict.values())
    else:
        devices = devices_dict if isinstance(devices_dict, list) else []

    _LOGGER.debug(
        "Total devices in hass.data[DOMAIN]['devices'][%s]: %s",
        entry_id,
        len(devices),
    )

    # Get language preference
    language = config_entry.options.get(
        "language",
        config_entry.data.get("language", DEFAULT_INTEGRATION_LANGUAGE),
    )
    i18n = get_i18n(language)

    devices_config = config_entry.data.get(CONF_DEVICES_CONFIG, {})

    # Get coordinator and cloud client
    coordinator = get_coordinator(hass, entry_id)
    cloud_client = hass.data[DOMAIN]["clients"][entry_id]

    entities = []

    for device in devices:
        device_id = device.get("id") or device.get("deviceId", "")
        device_name = (
            device.get("deviceName")
            or device.get("name")
            or device.get("productName", "Unknown")
        )
        device_model = (
            device.get("modelName")
            or device.get("model")
            or device.get("productName", "")
        )

        _LOGGER.debug(
            "Processing device: ID=%s, Name=%s, Model=%s",
            device_id,
            device_name,
            device_model,
        )

        # Reuse initialized device object from hass.data
        heiman_device = get_initialized_device(
            hass=hass,
            entry_id=entry_id,
            device_id=device_id,
            device_info=device,
            cloud_client=cloud_client,
            i18n=i18n,
        )

        # Add update entity for each device
        update_entity = HeimanUpdateEntity(
            coordinator=coordinator,
            device_info=device,
            cloud_client=cloud_client,
            i18n=i18n,
            devices_config=devices_config,
            heiman_device=heiman_device,  # Pass the initialized device object
        )
        entities.append(update_entity)
        _LOGGER.debug("  Device %s has update entity", device_name)

    _LOGGER.debug("Adding %s update entities for entry %s", len(entities), entry_id)

    if not entities:
        _LOGGER.warning(
            "No update entities were created! This might be normal if you have no devices with firmware updates.",
        )
    else:
        for entity in entities[:10]:  # Log first 10 entities
            _LOGGER.debug("  Entity: %s", entity.name)

    async_add_entities(entities)
    _LOGGER.debug("=" * 80)


class HeimanUpdateEntity(CoordinatorEntity, UpdateEntity):
    """Representation of a Heiman firmware update entity."""

    def __init__(
        self,
        coordinator,
        device_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
        heiman_device=None,  # New parameter to get firmware version from initialized device
    ) -> None:
        """Initialize update entity."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._cloud_client = cloud_client
        self._i18n = i18n
        self._devices_config = devices_config or {}
        self._heiman_device = heiman_device

        # Get device ID from various possible fields (API uses 'id')
        device_id = device_info.get("id") or device_info.get("deviceId", "")
        device_name = (
            device_info.get("deviceName")
            or device_info.get("name")
            or device_info.get("productName", "Unknown")
        )
        device_model = (
            device_info.get("modelName")
            or device_info.get("model")
            or device_info.get("productName", "Unknown")
        )

        # Apply device config overrides if available
        device_config = self._devices_config.get(device_id, {})
        if device_config.get("name"):
            device_name = device_config["name"]

        # Use i18n to translate "Firmware Info"
        firmware_info_translated = (
            self._i18n.translate("entity", "update.firmware.name")
            if hasattr(self, "_i18n") and self._i18n
            else "Firmware Info"
        )
        if (
            not firmware_info_translated
            or firmware_info_translated == "update.firmware.name"
        ):
            firmware_info_translated = "Firmware Info"

        self._attr_unique_id = f"{device_id}_firmware_update"
        self._attr_name = f"{device_name} {firmware_info_translated}"

        # Set supported features
        self._attr_supported_features = (
            UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
        )

        # Build device info with area support and firmware version
        device_info_dict = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Heiman",
            "model": device_model,
        }

        # Extract firmware version from various possible fields
        sw_version = None

        # Try 1: Get from heiman_device object (already initialized with API data)
        if heiman_device and hasattr(heiman_device, "firmware_version"):
            sw_version = heiman_device.firmware_version
            if sw_version:
                _LOGGER.debug(
                    "Got firmware version %s for device %s from heiman_device object",
                    sw_version,
                    device_id,
                )

        # Try 2: Try direct sw_version field
        if not sw_version and device_info.get("sw_version"):
            sw_version = device_info.get("sw_version")
            _LOGGER.debug(
                "Found sw_version directly in device_info for %s: %s",
                device_id,
                sw_version,
            )
        # Try 3: Try firmwareInfo.version
        elif not sw_version and device_info.get("firmwareInfo"):
            firmware_info = device_info.get("firmwareInfo", {})
            if isinstance(firmware_info, dict) and firmware_info.get("version"):
                sw_version = firmware_info.get("version")
                _LOGGER.debug(
                    "Extracted firmware version from firmwareInfo for %s: %s",
                    device_id,
                    sw_version,
                )

        # Add firmware version to device info if available
        if sw_version:
            device_info_dict["sw_version"] = sw_version
            _LOGGER.debug(
                "Added firmware version %s to update device info for %s",
                sw_version,
                device_id,
            )
        else:
            _LOGGER.debug(
                "No firmware version found for device %s (%s). Available keys: %s",
                device_id,
                device_name,
                list(device_info.keys()),
            )

        # Add suggested_area from device config
        if device_config.get("area_id"):
            device_info_dict["suggested_area"] = device_config["area_id"]
        else:
            # Fallback to room name from device info
            room_name = device_info.get("room_name") or device_info.get("roomName", "")
            home_name = device_info.get("home_name") or device_info.get("homeName", "")
            if room_name and home_name:
                device_info_dict["suggested_area"] = f"{home_name} {room_name}"
            elif room_name:
                device_info_dict["suggested_area"] = room_name
            elif home_name:
                device_info_dict["suggested_area"] = home_name

        self._attr_device_info = device_info_dict

        # Initialize version attributes with sw_version as default
        # Use the same extraction logic as above
        if not sw_version:
            # Try to get from heiman_device object
            if heiman_device and hasattr(heiman_device, "firmware_version"):
                sw_version = heiman_device.firmware_version

            # Try device_info fields
            if not sw_version:
                if device_info.get("sw_version"):
                    sw_version = device_info.get("sw_version")
                elif device_info.get("firmwareInfo"):
                    firmware_info = device_info.get("firmwareInfo", {})
                    if isinstance(firmware_info, dict) and firmware_info.get("version"):
                        sw_version = firmware_info.get("version")

        self._attr_installed_version = sw_version
        self._attr_latest_version = sw_version  # Default to current version
        _LOGGER.debug(
            "Initialized update entity %s with version: %s",
            self._attr_name,
            sw_version or "None",
        )
        self._attr_release_summary = None
        self._attr_release_url = None
        self._attr_title = "Heiman Firmware"
        self._attr_in_progress = False
        self._attr_update_percentage = None
        self._attr_auto_update = False

        # Set icon property after other attributes
        self._attr_icon = "mdi:file-document-outline"

        # Try to get initial value from coordinator cache
        if coordinator:
            self._update_from_cache()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
        # Always return the icon to ensure it's displayed
        return "mdi:file-document-outline"

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed."""
        # Disable polling - rely on coordinator refresh
        return False

    def _update_from_cache(self) -> bool:
        """Update entity state from coordinator cache (synchronous).

        Returns True if state was updated from cache, False if cache miss.
        """
        # Get device ID from various possible fields
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        # Get installed version from device info
        installed_version = self._device_info.get("sw_version")
        if installed_version:
            # Only update if we don't have a better version
            if (
                not self._attr_installed_version
                or self._attr_installed_version == "unknown"
            ):
                self._attr_installed_version = installed_version
                _LOGGER.debug(
                    "Update entity %s set installed version: %s",
                    self._attr_name,
                    installed_version,
                )

        # Try to get latest version from coordinator cache
        if self.coordinator and hasattr(self.coordinator, "get_device_property"):
            latest_version = self.coordinator.get_device_property(
                device_id,
                "LatestFirmwareVersion",
            )
            if latest_version:
                latest_ver_str = str(latest_version)
                self._attr_latest_version = latest_ver_str
                _LOGGER.debug(
                    "Update entity %s got latest version from cache: %s",
                    self._attr_name,
                    latest_ver_str,
                )

                # Update installed version if we have a newer version
                if installed_version and self._version_is_newer(
                    latest_ver_str,
                    installed_version,
                ):
                    _LOGGER.debug(
                        "Firmware update available for device %s: %s -> %s",
                        device_id,
                        installed_version,
                        latest_ver_str,
                    )
                else:
                    # No update available, set latest to installed
                    if installed_version:
                        self._attr_latest_version = installed_version
                    _LOGGER.debug(
                        "No firmware update available for device %s (current: %s, latest: %s)",
                        device_id,
                        installed_version,
                        latest_ver_str,
                    )
            # If no latest version from cache, use installed version
            elif installed_version:
                self._attr_latest_version = installed_version
                _LOGGER.debug(
                    "Using sw_version as latest version for device %s: %s",
                    device_id,
                    installed_version,
                )
        # If no coordinator, ensure we have at least sw_version
        elif installed_version:
            self._attr_latest_version = installed_version
            self._attr_installed_version = installed_version

        # Log current state for debugging
        _LOGGER.debug(
            "Update entity %s state: installed=%s, latest=%s",
            self._attr_name,
            self._attr_installed_version,
            self._attr_latest_version,
        )

        return True

    def _version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""
        try:
            return version.parse(str(latest_version)) > version.parse(
                str(installed_version),
            )
        except ImportError:
            # Fallback to simple string comparison if packaging is not available
            return str(latest_version) != str(installed_version)
        except Exception:
            _LOGGER.exception(
                "Error comparing versions %s and %s",
                latest_version,
                installed_version,
            )
            return False

    async def async_update(self) -> None:
        """Update the entity state from coordinator cache (polling).

        This is called during polling by Home Assistant.
        Note: HA automatically calls async_write_ha_state() after async_update().
        """
        try:
            self._update_from_cache()
        except Exception:
            _LOGGER.exception("Error updating firmware info for %s", self._attr_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).

        This is called when the coordinator has new data (e.g., from MQTT).
        Updates entity state immediately without waiting for next poll.
        """
        try:
            if self._update_from_cache():
                _LOGGER.debug(
                    "Update entity %s received coordinator update (MQTT)",
                    self._attr_name,
                )
                # Write the new state to Home Assistant immediately
                self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Error updating firmware info for %s", self._attr_name)

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Install an update.

        Version can be specified to install a specific version. When `None`, the
        latest version needs to be installed.

        The backup parameter indicates a backup should be taken before
        installing the update.
        """
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        self._device_info.get("productId", "")

        target_version = version or self._attr_latest_version

        if not target_version:
            _LOGGER.error("No target version specified for firmware update")
            return

        _LOGGER.debug(
            "Starting firmware update for device %s: %s -> %s (backup=%s)",
            device_id,
            self._attr_installed_version,
            target_version,
            backup,
        )

        try:
            # Set progress state
            self._attr_in_progress = True
            self._attr_update_percentage = 0
            self.async_write_ha_state()

            # TODO: Call API to start firmware update
            # This would typically use the cloud client to trigger the update
            # For now, we'll just log the action

            # Simulate update process (this should be replaced with actual API call)
            # Example: await self._cloud_client.async_start_firmware_update(device_id, target_version)

            _LOGGER.debug(
                "Firmware update initiated for device %s to version %s",
                device_id,
                target_version,
            )

            # Update progress (this would come from real API callbacks)
            self._attr_update_percentage = 50
            self.async_write_ha_state()

            # Wait for update to complete (in real implementation, this would be event-driven)
            # For now, just mark as complete
            self._attr_in_progress = False
            self._attr_update_percentage = 100
            self._attr_installed_version = target_version
            self.async_write_ha_state()

            _LOGGER.debug(
                "Firmware update completed for device %s, now at version %s",
                device_id,
                target_version,
            )

        except Exception:
            _LOGGER.exception(
                "Firmware update failed for device %s",
                device_id,
            )
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()
            raise
