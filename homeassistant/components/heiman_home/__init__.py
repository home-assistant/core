"""Heiman Cloud Home Assistant Integration.

Copyright (C) 2026 Heiman Cloud Home Assistant Integration

This integration provides connection to Heiman Cloud platform for device management.
"""

from __future__ import annotations

import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import ATTR_GATEWAY_DEVICE_ID, DOMAIN, PLATFORMS, SERVICE_SYNC_CHILD_DEVICES
from .device_management import DeviceManagementEnhanced
from .heiman_cloud import HeimanCloudClient
from .heiman_coordinator import (
    get_coordinator,
    register_coordinator,
    unregister_coordinator,
)
from .heiman_device import HeimanDevice
from .heiman_error import HeimanConfigError
from .heiman_i18n import HeimanI18n
from .heiman_mqtt import HeimanMqttClient

_LOGGER = logging.getLogger(__name__)


def _raise_no_homes_found() -> None:
    """Raise setup error when no homes are available."""
    raise HeimanConfigError("no_homes_found")


async def async_setup(hass: HomeAssistant, hass_config: dict) -> bool:
    """Set up the Heiman Home integration."""
    hass.data.setdefault(DOMAIN, {})
    # {[entry_id:str]: HeimanCloudClient}, heiman client instance
    hass.data[DOMAIN].setdefault("clients", {})
    # {[entry_id:str]: list[HeimanDevice]}
    hass.data[DOMAIN].setdefault("devices", {})
    # {[entry_id:str]: entities}
    hass.data[DOMAIN].setdefault("entities", {})
    for platform in PLATFORMS:
        hass.data[DOMAIN]["entities"][platform] = []

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a Heiman Home entry."""
    entry_id = config_entry.entry_id
    entry_data = dict(config_entry.data)

    _LOGGER.info("=" * 80)
    _LOGGER.info("Setting up Heiman Home entry: %s", entry_id)
    _LOGGER.info("=" * 80)

    def ha_persistent_notify(
        notify_id: str,
        title: str | None = None,
        message: str | None = None,
    ) -> None:
        """Send messages in Notifications dialog box."""
        if title:
            persistent_notification.async_create(
                hass=hass,
                message=message or "",
                title=title,
                notification_id=notify_id,
            )
        else:
            persistent_notification.async_dismiss(hass=hass, notification_id=notify_id)

    # Clear any previous error notifications
    ha_persistent_notify(notify_id=f"{entry_id}.auth_error", title=None, message=None)

    try:
        # Initialize cloud client
        cloud_client = HeimanCloudClient(
            hass=hass,
            entry_id=entry_id,
            config=entry_data,
            persistent_notify=ha_persistent_notify,
        )

        # Initialize device management
        device_management = DeviceManagementEnhanced()

        # Configure device management from entry data
        filter_config = {
            "filter_mode": entry_data.get("device_filter_mode", "exclude"),
            "statistics_logic": entry_data.get("statistics_logic", "or"),
            "room_filter_mode": entry_data.get("room_filter_mode", "exclude"),
            "room_list": entry_data.get("room_list", []),
            "type_filter_mode": entry_data.get("type_filter_mode", "exclude"),
            "type_list": entry_data.get("type_list", []),
            "model_filter_mode": entry_data.get("model_filter_mode", "exclude"),
            "model_list": entry_data.get("model_list", []),
            "device_filter_mode": entry_data.get("device_filter_mode", "exclude"),
            "device_list": entry_data.get("device_list", []),
        }

        display_config = {
            "hide_non_standard": entry_data.get("hide_non_standard_entities", False),
            "action_debug_mode": entry_data.get("action_debug_mode", False),
            "binary_sensor_display_mode": entry_data.get(
                "binary_sensor_display_mode",
                "bool",
            ),
            "display_devices_changed_notify": entry_data.get(
                "display_devices_changed_notify",
                [],
            ),
        }

        device_management.configure_all(
            filter_config=filter_config,
            display_config=display_config,
            area_sync_mode=entry_data.get("area_name_rule", "none"),
        )

        # Store device management in hass data
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN].setdefault("device_management", {})[entry_id] = (
            device_management
        )

        # Initialize HTTP client first (no need to call async_login)
        await cloud_client.async_initialize_http_client()

        _LOGGER.info("Heiman Cloud client initialized for entry: %s", entry_id)
        _LOGGER.debug("User ID: %s", cloud_client.user_id)
        _LOGGER.debug("API URL: %s", cloud_client.api_url)

        # Get home list
        _LOGGER.debug("Fetching home list from API...")
        homes = await cloud_client.async_get_homes()

        if not homes or not isinstance(homes, list):
            _LOGGER.error("No homes found for this account or invalid response format")
            _LOGGER.debug("Homes response: %s", homes)
            _raise_no_homes_found()

        _LOGGER.info("Found %s homes for account %s", len(homes), cloud_client.user_id)
        for home in homes:
            _LOGGER.debug(
                "  - Home ID: %s, Name: %s, Devices: %s",
                home.get("homeId"),
                home.get("homeName"),
                home.get("deviceCount", 0),
            )

        # Get homes list from config or API
        config_homes = entry_data.get("homes", {})
        selected_home_ids = entry_data.get("home_ids", [])

        if not selected_home_ids:
            _LOGGER.warning("No home_ids in config, will use first home from API")
            # Fall back to using first home from API response
            selected_home_id = homes[0].get("homeId")
            selected_home_ids = [selected_home_id]
        else:
            # Use the home_ids from config (multiple homes support)
            selected_home_id = (
                selected_home_ids[0] if selected_home_ids else homes[0].get("homeId")
            )

        _LOGGER.info("Selected home IDs: %s", selected_home_ids)
        _LOGGER.info("Primary home ID: %s", selected_home_id)

        # Get device list from ALL selected homes
        all_devices = {}

        for idx, home_id in enumerate(selected_home_ids):
            try:
                _LOGGER.info("=" * 80)
                _LOGGER.info(
                    "Fetching devices from home %d/%s: %s",
                    idx + 1,
                    len(selected_home_ids),
                    home_id,
                )
                _LOGGER.info("=" * 80)

                # Set home and get devices
                cloud_client.set_home(home_id)

                _LOGGER.debug("Calling async_get_devices() for home %s", home_id)

                devices = await cloud_client.async_get_devices()

                _LOGGER.debug("async_get_devices() returned: %s devices", len(devices))

                if devices:
                    _LOGGER.info("Found %s devices in home %s", len(devices), home_id)

                    # Apply device filters
                    devices_list = list(devices.values())
                    filtered_devices_list = (
                        device_management.filter_manager.get_filtered_devices(
                            devices_list,
                        )
                    )

                    # Convert back to dict
                    devices = {d.get("id"): d for d in filtered_devices_list}

                    # Merge devices (avoid duplicates by device ID)
                    all_devices.update(devices)
                else:
                    _LOGGER.warning("No devices found in home %s", home_id)

            except Exception as err:
                _LOGGER.error("Failed to get devices for home %s: %s", home_id, err)
                _LOGGER.exception(
                    "Traceback while getting devices for home %s", home_id
                )
                # Continue with other homes

        devices = all_devices

        _LOGGER.info("=" * 80)
        _LOGGER.info("Device loading summary")
        _LOGGER.info("=" * 80)
        total_device_count = len(devices)
        _LOGGER.info(
            "Total unique devices across all selected homes: %s",
            total_device_count,
        )

        # Log device distribution across homes
        if len(selected_home_ids) > 1:
            _LOGGER.info(
                "Devices are distributed across %s homes",
                len(selected_home_ids),
            )

        _LOGGER.info(
            "First 10 device IDs: %s",
            list(devices.keys())[:10] if devices else "None",
        )
        if len(devices) > 10:
            _LOGGER.debug("... and %s more device IDs", len(devices) - 10)

        if not devices:
            _LOGGER.warning("=" * 80)
            _LOGGER.warning("No devices found in ANY of the selected homes!")
            _LOGGER.warning("This will cause the integration to appear empty.")
            _LOGGER.warning("=" * 80)
            _LOGGER.warning("Possible causes:")
            _LOGGER.warning("  1. API call failed or returned unexpected response")
            _LOGGER.warning("  2. Token expired or invalid")
            _LOGGER.warning("  3. Network connectivity issues")
            _LOGGER.warning("  4. Selected homes have no devices")
            _LOGGER.warning("Troubleshooting:")
            _LOGGER.warning(
                "  - Check network connection to: %s",
                entry_data.get("api_url"),
            )
            _LOGGER.warning("  - Verify token is not expired")
            _LOGGER.warning("  - Try selecting different homes in config")
            _LOGGER.warning("=" * 80)

        # Store client and devices
        hass.data[DOMAIN]["clients"][entry_id] = cloud_client
        hass.data[DOMAIN]["devices"][entry_id] = devices

        _LOGGER.info(
            "Stored %s devices in hass.data[DOMAIN]['devices'][%s]",
            total_device_count,
            entry_id,
        )
        _LOGGER.info(
            "These %s devices will be managed by this integration entry",
            total_device_count,
        )

        # Clean up orphaned entities from previous failed attempts
        # This helps resolve issues with duplicate unique_ids and invalid entity configurations
        await _cleanup_orphaned_entities(hass, entry_id)

        # Update cloud client's all_devices cache for multi-home support
        # This ensures MQTT client can find parent devices across all homes
        cloud_client.set_all_devices(devices)
        _LOGGER.info(
            "Updated cloud_client all_devices cache with %s devices",
            len(devices),
        )

        # Initialize MQTT client
        mqtt_client = HeimanMqttClient(
            hass=hass,
            cloud_client=cloud_client,
            entry_id=entry_id,
            config=entry_data,
        )
        await mqtt_client.async_connect()

        # Store MQTT client
        cloud_client.mqtt_client = mqtt_client

        # Start token auto-refresh
        await cloud_client.start_token_refresh()

        # Create and register coordinator
        coordinator = get_coordinator(hass, entry_id)
        coordinator.set_cloud_client(cloud_client)
        # Use set_mqtt_client to properly register callbacks
        coordinator.set_mqtt_client(mqtt_client)
        register_coordinator(entry_id, coordinator)

        # Set coordinator reference in MQTT client for cache updates
        mqtt_client.set_coordinator(coordinator)
        _LOGGER.debug("Set coordinator reference in MQTT client")

        # Pre-register device properties before first refresh
        # This ensures batch property fetching works during initial data load
        i18n = HeimanI18n(language=entry_data.get("integration_language", "en"))
        _LOGGER.info("Pre-registering device properties for %s devices", len(devices))

        # Create device objects and initialize properties asynchronously
        # Store them in hass.data for reuse in platform setup
        initialized_devices = {}

        for device_id, device_info in devices.items():
            try:
                # Debug: Log the full device info structure to check for firmwareInfo
                _LOGGER.debug(
                    "Device %s info keys: %s",
                    device_id,
                    list(device_info.keys()),
                )

                # Extract firmware version from firmwareInfo if available in device list
                firmware_info = device_info.get("firmwareInfo", {})
                _LOGGER.debug(
                    "Device %s firmwareInfo: %s (type: %s)",
                    device_id,
                    firmware_info,
                    type(firmware_info),
                )

                if isinstance(firmware_info, dict) and "version" in firmware_info:
                    # Add firmware version to device_info for sw_version matching
                    device_info["sw_version"] = firmware_info.get("version")
                    _LOGGER.info(
                        "Extracted firmware version %s for device %s from firmwareInfo in device list",
                        firmware_info.get("version"),
                        device_id,
                    )
                else:
                    _LOGGER.debug(
                        "Device %s: firmwareInfo not available or invalid in device list",
                        device_id,
                    )
                heiman_device = HeimanDevice(
                    hass=hass,
                    device_info=device_info,
                    cloud_client=cloud_client,
                    entry_id=entry_id,
                    i18n=i18n,
                )

                # Initialize properties asynchronously
                await heiman_device.async_init_properties()

                # Store the initialized device object
                initialized_devices[device_id] = heiman_device

                # Register sensor properties
                sensor_entities = heiman_device.get_sensor_entities()
                binary_sensor_entities = heiman_device.get_binary_sensor_entities()
                switch_entities = heiman_device.get_switch_entities()
                button_entities = heiman_device.get_button_entities()

                total_registered = (
                    len(sensor_entities)
                    + len(binary_sensor_entities)
                    + len(switch_entities)
                    + len(button_entities)
                )
                if total_registered > 0:
                    _LOGGER.debug(
                        "Pre-registered %s properties for device %s (sensor: %d, binary_sensor: %d, switch: %d, button: %d)",
                        total_registered,
                        device_id,
                        len(sensor_entities),
                        len(binary_sensor_entities),
                        len(switch_entities),
                        len(button_entities),
                    )

            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to pre-register properties for device %s: %s",
                    device_id,
                    err,
                )

        # Store initialized devices in hass.data for platform reuse
        hass.data[DOMAIN]["heiman_devices"] = hass.data[DOMAIN].get(
            "heiman_devices",
            {},
        )
        hass.data[DOMAIN]["heiman_devices"][entry_id] = initialized_devices
        _LOGGER.info(
            "Stored %s initialized device objects in hass.data",
            len(initialized_devices),
        )

        _LOGGER.info("Completed pre-registration of device properties")

        # Initial data refresh (now with pre-registered properties)
        await coordinator.async_config_entry_first_refresh()

        # Setup platforms
        _LOGGER.warning("=" * 80)
        _LOGGER.warning("PLATFORMS constant value: %s", PLATFORMS)
        _LOGGER.warning("PLATFORMS type: %s", type(PLATFORMS))
        _LOGGER.warning(
            "PLATFORMS length: %d",
            len(PLATFORMS) if isinstance(PLATFORMS, (list, tuple)) else "N/A",
        )
        for idx, platform in enumerate(PLATFORMS):
            _LOGGER.warning(
                "PLATFORMS[%d] = %s (type: %s)",
                idx,
                platform,
                type(platform),
            )
        _LOGGER.warning("=" * 80)
        _LOGGER.warning(
            "About to call async_forward_entry_setups with entry_id=%s",
            entry_id,
        )
        _LOGGER.info("Setting up platforms: %s", PLATFORMS)
        # Note: async_forward_entry_setups performs synchronous module imports,
        # which triggers a warning from Home Assistant's loop detector.
        # This is expected behavior and does not affect functionality.
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
        _LOGGER.warning("async_forward_entry_setups completed successfully")

        # Register refresh service for this entry
        service_name = f"{DOMAIN}_refresh_{entry_id[:8]}"
        hass.services.async_register(
            DOMAIN,
            f"refresh_{entry_id[:8]}",
            lambda call: _handle_refresh_service(hass, entry_id, call),
            schema=None,
        )
        _LOGGER.info(
            "Registered refresh service: %s.%s",
            DOMAIN,
            f"refresh_{entry_id[:8]}",
        )

        # Register remove device service for this entry
        hass.services.async_register(
            DOMAIN,
            f"remove_device_{entry_id[:8]}",
            lambda call: _handle_remove_device_service(hass, entry_id, call),
            schema=None,
        )
        _LOGGER.info(
            "Registered remove device service: %s.%s",
            DOMAIN,
            f"remove_device_{entry_id[:8]}",
        )

        _LOGGER.info("=" * 80)
        _LOGGER.info("Successfully set up Heiman Home entry: %s", entry_id)
        _LOGGER.info("=" * 80)

    except Exception as err:
        _LOGGER.error("=" * 80)
        _LOGGER.error("Failed to setup entry: %s", err)
        _LOGGER.error("=" * 80)
        _LOGGER.exception("Full traceback")

        # Clean up cloud client on error
        if "cloud_client" in locals() and cloud_client:
            try:
                await cloud_client.async_close()
            except Exception as cleanup_err:  # noqa: BLE001
                _LOGGER.warning("Failed to cleanup cloud client: %s", cleanup_err)

        ha_persistent_notify(
            notify_id=f"{entry_id}.auth_error",
            title="Heiman Home Auth Error",
            message=f"Please re-authenticate.\nError: {err}",
        )
        return False

    return True


async def _handle_remove_device_service(
    hass: HomeAssistant,
    entry_id: str,
    call,
) -> None:
    """Handle the remove device service call.

    This service removes a device and optionally its entities from the integration.
    """
    _LOGGER.info("Remove device service called for entry: %s", entry_id)

    device_id = call.data.get("device_id")
    remove_entities = call.data.get("remove_entities", True)

    if not device_id:
        _LOGGER.error("Device ID is required for remove_device service")
        return

    try:
        # Get devices list
        devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})
        if isinstance(devices_dict, dict):
            devices = list(devices_dict.values())
        else:
            devices = devices_dict if isinstance(devices_dict, list) else []

        # Check if device exists
        device_exists = any(
            (d.get("id") == device_id or d.get("deviceId") == device_id)
            for d in devices
        )

        if not device_exists:
            _LOGGER.warning("Device %s not found in entry %s", device_id, entry_id)
            return

        # Remove device from devices list
        if isinstance(hass.data[DOMAIN]["devices"][entry_id], dict):
            hass.data[DOMAIN]["devices"][entry_id].pop(device_id, None)
        else:
            hass.data[DOMAIN]["devices"][entry_id] = [
                d
                for d in hass.data[DOMAIN]["devices"][entry_id]
                if d.get("id") != device_id and d.get("deviceId") != device_id
            ]

        _LOGGER.info("Removed device %s from entry %s", device_id, entry_id)

        # Remove entities if requested
        if remove_entities:
            entity_registry_helper = er.async_get(hass)
            device_registry_helper = dr.async_get(hass)

            # Get device registry entry
            device_reg_entry = device_registry_helper.async_get_device(
                identifiers={(DOMAIN, device_id)},
                connections=None,
            )

            if device_reg_entry:
                # Remove all entities associated with this device
                entities_to_remove = (
                    entity_registry_helper.entities.get_entries_for_device(
                        device_id=device_reg_entry.id,
                    )
                )

                for entity_entry in entities_to_remove:
                    entity_registry_helper.async_remove(entity_entry.entity_id)
                    _LOGGER.debug("Removed entity: %s", entity_entry.entity_id)

                # Remove device from registry
                device_registry_helper.async_remove_device(device_reg_entry.id)
                _LOGGER.info(
                    "Removed device %s and %s associated entities from registry",
                    device_id,
                    len(entities_to_remove),
                )
            else:
                _LOGGER.debug("Device %s not found in device registry", device_id)

        # Also remove from initialized devices cache
        heiman_devices = hass.data[DOMAIN].get("heiman_devices", {}).get(entry_id, {})
        if device_id in heiman_devices:
            heiman_devices.pop(device_id)
            _LOGGER.debug("Removed device %s from heiman_devices cache", device_id)

        _LOGGER.info("Device %s removal completed successfully", device_id)

    except Exception:
        _LOGGER.exception("Error removing device %s", device_id)


async def _handle_refresh_service(hass: HomeAssistant, entry_id: str, call) -> None:
    """Handle the refresh service call.

    This service triggers an immediate refresh of all device data.
    """
    _LOGGER.info("Refresh service called for entry: %s", entry_id)

    coordinator = get_coordinator(hass, entry_id)
    if coordinator:
        try:
            # Force a refresh of coordinator data
            await coordinator.async_request_refresh()
            _LOGGER.info("Coordinator refresh completed for entry: %s", entry_id)

            # Optionally refresh all entity states explicitly
            entities = hass.data.get(DOMAIN, {}).get("entities", {})
            for platform_entities in entities.values():
                if isinstance(platform_entities, dict):
                    # New format: {entry_id: [entities]}
                    entry_entities = platform_entities.get(entry_id, [])
                elif isinstance(platform_entities, list):
                    # Old format: list of entities
                    entry_entities = [
                        e
                        for e in platform_entities
                        if hasattr(e, "registry_entry")
                        and e.registry_entry
                        and e.registry_entry.config_entry_id == entry_id
                    ]
                else:
                    entry_entities = []

                for entity in entry_entities:
                    if hasattr(entity, "async_update"):
                        try:
                            _LOGGER.info("Updating entity: %s", entity.entity_id)
                            await entity.async_update()
                            _LOGGER.debug("Refreshed entity: %s", entity.entity_id)
                        except Exception as err:  # noqa: BLE001
                            _LOGGER.warning(
                                "Failed to refresh entity %s: %s",
                                entity.entity_id,
                                err,
                            )

            _LOGGER.info("Refresh service completed for entry: %s", entry_id)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Refresh service failed for entry %s: %s", entry_id, err)
    else:
        _LOGGER.warning("No coordinator found for entry: %s", entry_id)

    # Register sync_child_devices service for this entry
    async def handle_sync_child_devices(call):
        """Handle child device sync service call."""
        gateway_device_id = call.data.get(ATTR_GATEWAY_DEVICE_ID)

        if not gateway_device_id:
            _LOGGER.error(
                "gateway_device_id is required for sync_child_devices service",
            )
            return

        coordinator = get_coordinator(hass, entry_id)
        if not coordinator:
            _LOGGER.error("No coordinator found for entry %s", entry_id)
            return

        try:
            _LOGGER.info("Syncing child devices for gateway: %s", gateway_device_id)
            success = await coordinator.async_sync_child_devices(gateway_device_id)
            if success:
                _LOGGER.info(
                    "Child device sync completed successfully for gateway %s",
                    gateway_device_id,
                )
            else:
                _LOGGER.warning(
                    "Child device sync failed for gateway %s",
                    gateway_device_id,
                )
        except Exception:
            _LOGGER.exception("Error syncing child devices")

    service_name_sync = f"{SERVICE_SYNC_CHILD_DEVICES}_{entry_id[:8]}"
    hass.services.async_register(DOMAIN, service_name_sync, handle_sync_child_devices)
    _LOGGER.info("Registered sync service: %s.%s", DOMAIN, service_name_sync)


async def _cleanup_orphaned_entities(hass: HomeAssistant, entry_id: str) -> None:
    """Clean up orphaned entities from previous failed setup attempts.

    This removes entities that:
    1. Have duplicate unique_ids (caused by re-setup attempts)
    2. Have invalid configurations (e.g., enum type with unit)
    3. Are no longer present in current device list

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
    """
    entity_registry_helper = er.async_get(hass)

    # Get all entities for this entry
    existing_entities = er.async_entries_for_config_entry(
        entity_registry_helper,
        entry_id,
    )

    removed_count = 0
    duplicate_count = 0

    # Track unique IDs we've seen
    seen_unique_ids = set()

    for entity_entry in existing_entities:
        try:
            # Check for duplicates (same unique_id)
            if entity_entry.unique_id in seen_unique_ids:
                _LOGGER.debug(
                    "Removing duplicate entity: %s (unique_id: %s)",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                entity_registry_helper.async_remove(entity_entry.entity_id)
                duplicate_count += 1
                removed_count += 1
                continue

            seen_unique_ids.add(entity_entry.unique_id)

            # Check for known problematic patterns
            # Entities with 'state', 'online_status', 'device_type' that may have invalid config
            unique_id_lower = entity_entry.unique_id.lower()
            if any(
                pattern in unique_id_lower
                for pattern in ["_state", "online_status", "device_type"]
            ):
                _LOGGER.debug(
                    "Removing potentially invalid entity: %s (unique_id: %s)",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                entity_registry_helper.async_remove(entity_entry.entity_id)
                removed_count += 1
                continue

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to process entity %s during cleanup: %s",
                entity_entry.entity_id,
                err,
            )

    if removed_count > 0:
        _LOGGER.info(
            "Cleaned up %s orphaned/duplicate entities for entry %s (%s duplicates)",
            removed_count,
            entry_id,
            duplicate_count,
        )


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a Heiman Home entry."""
    entry_id = config_entry.entry_id

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry,
        PLATFORMS,
    )

    if unload_ok:
        hass.data[DOMAIN]["entities"].pop(entry_id, None)
        hass.data[DOMAIN]["devices"].pop(entry_id, None)

    # Disconnect MQTT
    cloud_client = hass.data[DOMAIN]["clients"].pop(entry_id, None)
    if cloud_client:
        # Stop token refresh
        await cloud_client.stop_token_refresh()

        if cloud_client.mqtt_client:
            await cloud_client.mqtt_client.async_disconnect()
        await cloud_client.async_close()

    # Remove device management
    hass.data[DOMAIN].get("device_management", {}).pop(entry_id, None)

    # Unregister coordinator
    unregister_coordinator(entry_id)

    # Stop refresh optimizer
    device_management = (
        hass.data[DOMAIN].get("device_management", {}).pop(entry_id, None)
    )
    if device_management:
        try:
            # Cleanup any resources
            pass
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to cleanup device management: %s", err)

    # Unregister refresh service
    service_name = f"refresh_{entry_id[:8]}"
    hass.services.async_remove(DOMAIN, service_name)
    _LOGGER.info("Unregistered refresh service: %s.%s", DOMAIN, service_name)

    # Unregister sync service
    service_name_sync = f"{SERVICE_SYNC_CHILD_DEVICES}_{entry_id[:8]}"
    hass.services.async_remove(DOMAIN, service_name_sync)
    _LOGGER.info("Unregistered sync service: %s.%s", DOMAIN, service_name_sync)

    return True


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Remove a Heiman Home entry."""
    dict(config_entry.data)

    # Clean up stored data
    cloud_client = hass.data[DOMAIN]["clients"].get(config_entry.entry_id)
    if cloud_client:
        await cloud_client.async_close()

    return True


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload a Heiman Home entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
