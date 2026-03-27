"""The Grandstream Home integration."""

import asyncio
import logging
from typing import Any

from grandstream_home_api import GDSPhoneAPI, GNSNasAPI
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_DEVICE_MODEL,
    CONF_DEVICE_TYPE,
    CONF_FIRMWARE_VERSION,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRODUCT_MODEL,
    CONF_USE_HTTPS,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTPS_PORT,
    DEFAULT_PORT,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
)
from .coordinator import GrandstreamCoordinator
from .device import GDSDevice, GNSNASDevice
from .error import GrandstreamHAControlDisabledError
from .utils import decrypt_password, generate_unique_id

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type GrandstreamConfigEntry = ConfigEntry[dict[str, Any]]

# Device type mapping to API classes
DEVICE_API_MAPPING = {
    DEVICE_TYPE_GDS: GDSPhoneAPI,
    DEVICE_TYPE_GNS_NAS: GNSNasAPI,
}

# Device type mapping to device classes
DEVICE_CLASS_MAPPING = {
    DEVICE_TYPE_GDS: GDSDevice,
    DEVICE_TYPE_GNS_NAS: GNSNASDevice,
}


async def _setup_api(hass: HomeAssistant, entry: ConfigEntry) -> Any:
    """Set up and initialize API."""
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_GDS)

    # Get API class using mapping, default to GDS if unknown type
    api_class = DEVICE_API_MAPPING.get(device_type, GDSPhoneAPI)

    # Create API instance based on device type
    api = _create_api_instance(api_class, device_type, entry)

    # Initialize global API lock if not exists
    hass.data.setdefault(DOMAIN, {})
    if "api_lock" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["api_lock"] = asyncio.Lock()

    # Attempt login with error handling
    try:
        await _attempt_api_login(hass, api)
    except GrandstreamHAControlDisabledError as e:
        _LOGGER.error("HA control disabled during API setup: %s", e)
        raise ConfigEntryAuthFailed(
            "Home Assistant control is disabled on the device"
        ) from e

    return api


def _create_api_instance(api_class, device_type: str, entry: ConfigEntry) -> Any:
    """Create API instance based on device type."""
    host = entry.data.get("host", "")
    username = entry.data.get(CONF_USERNAME, "")
    encrypted_password = entry.data.get(CONF_PASSWORD, "")
    password = decrypt_password(encrypted_password, entry.unique_id or "default")
    use_https = entry.data.get(CONF_USE_HTTPS, True)
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)

    if device_type == DEVICE_TYPE_GDS:
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        return api_class(
            host=host,
            username=username,
            password=password,
            port=port,
            verify_ssl=verify_ssl,
        )

    if device_type == DEVICE_TYPE_GNS_NAS:
        port = entry.data.get(
            CONF_PORT, DEFAULT_HTTPS_PORT if use_https else DEFAULT_HTTP_PORT
        )
        return api_class(
            host,
            username,
            password,
            port=port,
            use_https=use_https,
            verify_ssl=verify_ssl,
        )

    # Default fallback
    return api_class(host, username, password)


async def _attempt_api_login(hass: HomeAssistant, api: Any) -> None:
    """Attempt to login to device API with error handling."""
    async with hass.data[DOMAIN]["api_lock"]:
        try:
            success = await hass.async_add_executor_job(api.login)
            if not success:
                # Check if HA control is disabled on device
                if (
                    hasattr(api, "is_ha_control_enabled")
                    and not api.is_ha_control_enabled
                ):
                    _raise_ha_control_disabled()

                # Check if account is locked (temporary condition)
                if hasattr(api, "_account_locked") and getattr(
                    api, "_account_locked", False
                ):
                    _LOGGER.warning(
                        "Account is temporarily locked, integration will retry later"
                    )
                    return  # Don't raise auth failed for temporary locks

                _raise_auth_failed()
        except GrandstreamHAControlDisabledError as e:
            _LOGGER.error("Caught GrandstreamHAControlDisabledError: %s", e)
            _raise_ha_control_disabled()
        except ConfigEntryAuthFailed:
            raise  # Re-raise auth failures
        except (ImportError, AttributeError, ValueError) as e:
            _LOGGER.warning(
                "API setup encountered error (device may be offline): %s, integration will continue to load",
                e,
            )


def _raise_auth_failed() -> None:
    """Raise authentication failed exception."""
    _LOGGER.error("Authentication failed - invalid credentials")
    raise ConfigEntryAuthFailed("Authentication failed - invalid credentials")


def _raise_ha_control_disabled() -> None:
    """Raise HA control disabled exception."""
    _LOGGER.error("Home Assistant control is disabled on the device")
    raise ConfigEntryAuthFailed(
        "Home Assistant control is disabled on the device. "
        "Please enable it in the device web interface."
    )


async def _setup_device(
    hass: HomeAssistant, entry: ConfigEntry, device_type: str
) -> Any:
    """Set up device instance."""
    # Get device class using mapping, default to GDS if unknown type
    device_class = DEVICE_CLASS_MAPPING.get(device_type, GDSDevice)

    # Extract device basic information
    device_info = {
        "host": entry.data.get("host", ""),
        "port": entry.data.get("port", "80"),
        "name": entry.data.get("name", ""),
    }

    # Get API instance for MAC address retrieval
    api = entry.runtime_data.get("api")

    # Extract MAC address from API if available
    mac_address = _extract_mac_address(api)
    _LOGGER.debug("Extracted MAC address: %s", mac_address)

    # Use config entry's unique_id (set during config flow, may be MAC-based)
    # This ensures consistency between config entry and device
    unique_id = entry.unique_id
    if not unique_id:
        # Fallback: generate unique_id from device info (should not happen)
        unique_id = generate_unique_id(
            device_info["name"], device_type, device_info["host"], device_info["port"]
        )
    _LOGGER.info(
        "Device unique ID: %s, name: %s, type: %s",
        unique_id,
        device_info["name"],
        device_type,
    )

    # Handle existing device
    await _handle_existing_device(hass, unique_id, device_info["name"], device_type)

    # Get device_model and product_model from config entry
    device_model = entry.data.get(CONF_DEVICE_MODEL, device_type)
    product_model = entry.data.get(CONF_PRODUCT_MODEL)

    # Create device instance
    device = device_class(
        hass=hass,
        name=device_info["name"],
        unique_id=unique_id,
        config_entry_id=entry.entry_id,
        device_model=device_model,
        product_model=product_model,
    )

    # Set device network information
    _set_device_network_info(device, api, device_info)

    return device


def _extract_mac_address(api: Any) -> str:
    """Extract MAC address from API if available."""
    if not api or not hasattr(api, "device_mac") or not api.device_mac:
        return ""

    mac_address = api.device_mac.replace(":", "").upper()
    _LOGGER.info("Got MAC address from API: %s", mac_address)
    return mac_address


async def _handle_existing_device(
    hass: HomeAssistant, unique_id: str, name: str, device_type: str
) -> None:
    """Check and update existing device if found."""
    device_registry = dr.async_get(hass)

    for dev in device_registry.devices.values():
        for identifier in dev.identifiers:
            if identifier[0] == DOMAIN and identifier[1] == unique_id:
                _LOGGER.info("Found existing device: %s, name: %s", dev.id, dev.name)

                # Update device attributes
                device_registry.async_update_device(
                    dev.id,
                    name=name,
                    manufacturer="Grandstream",
                    model=device_type,
                )
                return


def _set_device_network_info(
    device: Any, api: Any, device_info: dict[str, str]
) -> None:
    """Set device network information (IP and MAC addresses)."""
    # Set IP address
    if api and hasattr(api, "host") and api.host:
        _LOGGER.info("Setting device IP address: %s", api.host)
        device.set_ip_address(api.host)
    else:
        _LOGGER.info("Using configured host address as IP: %s", device_info["host"])
        device.set_ip_address(device_info["host"])

    # Set MAC address if available
    if api and hasattr(api, "device_mac") and api.device_mac:
        _LOGGER.info("Setting device MAC address: %s", api.device_mac)
        device.set_mac_address(api.device_mac)


async def async_setup_entry(hass: HomeAssistant, entry: GrandstreamConfigEntry) -> bool:
    """Set up Grandstream Home integration."""
    try:
        _LOGGER.debug("Starting integration initialization: %s", entry.entry_id)

        # Extract device type from entry
        device_type = entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_GDS)

        # 1. Set up API
        api = await _setup_api_with_error_handling(hass, entry, device_type)

        # Store API in runtime_data (required for Bronze quality scale)
        entry.runtime_data = {"api": api}

        # 2. Create device instance
        device = await _setup_device(hass, entry, device_type)
        _LOGGER.debug(
            "Device created successfully: %s, unique ID: %s",
            device.name,
            device.unique_id,
        )

        # 3. Initialize data storage
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = {}

        # 4. Create coordinator
        coordinator = await _setup_coordinator(hass, device_type, entry)

        # 5. Update stored data
        await _update_stored_data(hass, entry, coordinator, device, device_type)

        # 6. Set up platforms
        await _setup_platforms(hass, entry)

        # 7. Update device information from API (for GNS devices)
        discovery_version = entry.data.get(CONF_FIRMWARE_VERSION)
        await _update_device_info_from_api(
            hass, api, device_type, device, discovery_version
        )

        _LOGGER.info("Integration initialization completed")
    except ConfigEntryAuthFailed:
        raise  # Let auth failures propagate to trigger reauth flow
    except Exception as e:
        _LOGGER.exception("Error setting up integration")
        raise ConfigEntryNotReady("Integration setup failed") from e
    return True


async def _setup_api_with_error_handling(
    hass: HomeAssistant, entry: ConfigEntry, device_type: str
) -> Any:
    """Set up API with error handling."""
    _LOGGER.debug("Starting API setup")
    try:
        # Authentication is handled in _attempt_api_login, just pass through any exceptions
        api = await _setup_api(hass, entry)
    except GrandstreamHAControlDisabledError as e:
        _LOGGER.error("HA control disabled: %s", e)
        raise ConfigEntryAuthFailed(
            "Home Assistant control is disabled on the device"
        ) from e
    except ConfigEntryAuthFailed:
        raise  # Re-raise auth failures
    except (ImportError, AttributeError, ValueError) as e:
        _LOGGER.exception("Error during API setup")
        raise ConfigEntryNotReady(f"API setup failed: {e}") from e
    else:
        _LOGGER.debug("API setup successful, device type: %s", device_type)
        return api


async def _setup_coordinator(
    hass: HomeAssistant, device_type: str, entry: ConfigEntry
) -> Any:
    """Set up data coordinator."""
    _LOGGER.debug("Starting coordinator creation")
    coordinator = GrandstreamCoordinator(hass, device_type, entry)
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Coordinator initialization completed")
    return coordinator


async def _update_stored_data(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: Any,
    device: Any,
    device_type: str,
) -> None:
    """Update stored data in hass.data."""
    _LOGGER.debug("Starting data storage update")
    try:
        # Get API from runtime_data
        api = entry.runtime_data.get("api") if entry.runtime_data else None

        # Get device_model from entry.data (stores original model: GDS/GSC/GNS)
        device_model = entry.data.get(CONF_DEVICE_MODEL, device_type)

        # Get product_model from entry.data (specific model: GDS3725, GDS3727, GSC3560)
        product_model = entry.data.get(CONF_PRODUCT_MODEL)

        hass.data[DOMAIN][entry.entry_id].update(
            {
                "api": api,
                "coordinator": coordinator,
                "device": device,
                "device_type": device_type,
                "device_model": device_model,
                "product_model": product_model,
            }
        )
        _LOGGER.debug("Data storage update successful")
    except (ImportError, AttributeError, ValueError) as e:
        _LOGGER.exception("Error during data update")
        raise ConfigEntryNotReady(f"Data storage update failed: {e}") from e


async def _setup_platforms(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up all platforms."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _update_device_info_from_api(
    hass: HomeAssistant,
    api: Any,
    device_type: str,
    device: Any,
    discovery_version: str | None = None,
) -> None:
    """Update device information from API for GNS devices."""
    if (
        device_type != DEVICE_TYPE_GNS_NAS
        or not api
        or not hasattr(api, "get_system_info")
    ):
        # For GDS devices, just set discovery version if available
        if discovery_version:
            device.set_firmware_version(discovery_version)
        return

    try:
        _LOGGER.debug("Getting additional device info from API")
        system_info = await hass.async_add_executor_job(api.get_system_info)

        if not system_info:
            return

        # Update device name with model if needed
        _update_device_name(device, system_info)

        # Update firmware version if available
        _update_firmware_version(device, api, system_info, discovery_version)

    except (OSError, ValueError, RuntimeError) as e:
        _LOGGER.warning("Failed to get additional device info from API: %s", e)


def _update_device_name(device: Any, system_info: dict[str, str]) -> None:
    """Update device name with model information if needed."""
    product_name = system_info.get("product_name", "")
    current_name = device.name

    # If device name doesn't contain model info, try to add model
    if product_name and not any(
        model in current_name for model in (DEVICE_TYPE_GNS_NAS, DEVICE_TYPE_GDS)
    ):
        # Construct new device name including model info
        new_name = f"{product_name.upper()}"
        _LOGGER.info(
            "Updating device name from %s to %s with model info", current_name, new_name
        )

        # Update device instance name and registration info
        device.name = new_name
        # Use public method if available instead of accessing private method
        if hasattr(device, "register_device"):
            device.register_device()


def _update_firmware_version(
    device: Any,
    api: Any,
    system_info: dict[str, str],
    discovery_version: str | None = None,
) -> None:
    """Update device firmware version from API or system info."""
    # First try from system info
    product_version = system_info.get("product_version", "")
    if product_version:
        _LOGGER.info("Setting device firmware version: %s", product_version)
        device.set_firmware_version(product_version)
        return

    # Fallback to API version attribute
    if hasattr(api, "version") and api.version:
        _LOGGER.debug("Setting device firmware version from API: %s", api.version)
        device.set_firmware_version(api.version)
        return

    # Fallback to discovery version
    if discovery_version:
        _LOGGER.debug(
            "Setting device firmware version from discovery: %s", discovery_version
        )
        device.set_firmware_version(discovery_version)


async def async_unload_entry(
    hass: HomeAssistant, entry: GrandstreamConfigEntry
) -> bool:
    """Unload config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
