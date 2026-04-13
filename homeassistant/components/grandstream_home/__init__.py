"""The Grandstream Home integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from grandstream_home_api import (
    attempt_login,
    create_api_instance,
    decrypt_password,
    generate_unique_id,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    CONF_DEVICE_MODEL,
    CONF_DEVICE_TYPE,
    CONF_FIRMWARE_VERSION,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRODUCT_MODEL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
)
from .coordinator import GrandstreamCoordinator
from .device import GDSDevice, GNSNASDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@dataclass
class GrandstreamRuntimeData:
    """Runtime data for Grandstream config entry."""

    api: Any
    coordinator: GrandstreamCoordinator
    device: GDSDevice | GNSNASDevice
    device_type: str
    device_model: str
    product_model: str | None


type GrandstreamConfigEntry = ConfigEntry[GrandstreamRuntimeData]

# Device type mapping to device classes
DEVICE_CLASS_MAPPING = {
    DEVICE_TYPE_GDS: GDSDevice,
    DEVICE_TYPE_GNS_NAS: GNSNASDevice,
}


async def _setup_api(hass: HomeAssistant, entry: ConfigEntry) -> Any:
    """Set up and initialize API."""
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_GDS)
    host = entry.data.get("host", "")
    username = entry.data.get(CONF_USERNAME, "")
    encrypted_password = entry.data.get(CONF_PASSWORD, "")
    password = decrypt_password(encrypted_password, entry.unique_id or "default")
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)

    # Create API instance using library function
    api = create_api_instance(
        device_type=device_type,
        host=host,
        username=username,
        password=password,
        port=port,
        verify_ssl=verify_ssl,
    )

    # Initialize global API lock if not exists
    hass.data.setdefault(DOMAIN, {})
    if "api_lock" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["api_lock"] = asyncio.Lock()

    # Attempt login with error handling
    await _attempt_api_login(hass, api)

    return api


async def _attempt_api_login(hass: HomeAssistant, api: Any) -> None:
    """Attempt to login to device API with error handling."""
    async with hass.data[DOMAIN]["api_lock"]:
        success, error_type = await hass.async_add_executor_job(attempt_login, api)

        if success:
            return

        if error_type == "offline":
            _LOGGER.warning("API login failed (device may be offline)")
            return

        if error_type == "ha_control_disabled":
            raise ConfigEntryAuthFailed(
                "Home Assistant control is disabled on the device. "
                "Please enable it in the device web interface."
            )

        if error_type == "account_locked":
            _LOGGER.warning(
                "Account is temporarily locked, integration will retry later"
            )
            return

        raise ConfigEntryAuthFailed("Authentication failed - invalid credentials")


async def _setup_device(
    hass: HomeAssistant, entry: ConfigEntry, device_type: str, api: Any
) -> Any:
    """Set up device instance."""
    device_class = DEVICE_CLASS_MAPPING.get(device_type, GDSDevice)
    name = entry.data.get("name", "")

    unique_id = entry.unique_id or generate_unique_id(
        name, device_type, entry.data.get("host", ""), entry.data.get("port", "80")
    )

    device = device_class(
        hass=hass,
        name=name,
        unique_id=unique_id,
        config_entry_id=entry.entry_id,
        device_model=entry.data.get(CONF_DEVICE_MODEL, device_type),
        product_model=entry.data.get(CONF_PRODUCT_MODEL),
    )

    # Set device network information
    if api and hasattr(api, "host") and api.host:
        device.set_ip_address(api.host)
    else:
        device.set_ip_address(entry.data.get("host", ""))

    if api and hasattr(api, "device_mac") and api.device_mac:
        device.set_mac_address(api.device_mac)

    return device


async def async_setup_entry(hass: HomeAssistant, entry: GrandstreamConfigEntry) -> bool:
    """Set up Grandstream Home integration."""
    _LOGGER.debug("Starting integration initialization: %s", entry.entry_id)

    # Extract device type from entry
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_GDS)

    # 1. Set up API
    api = await _setup_api_with_error_handling(hass, entry, device_type)

    # 2. Create device instance
    device = await _setup_device(hass, entry, device_type, api)

    # Get device_model and product_model from config entry
    device_model = entry.data.get(CONF_DEVICE_MODEL, device_type)
    product_model = entry.data.get(CONF_PRODUCT_MODEL)
    discovery_version = entry.data.get(CONF_FIRMWARE_VERSION)

    # 3. Create coordinator (pass discovery_version for firmware fallback)
    coordinator = GrandstreamCoordinator(hass, device_type, entry, discovery_version)

    # 4. Store runtime data BEFORE first refresh
    entry.runtime_data = GrandstreamRuntimeData(
        api=api,
        coordinator=coordinator,
        device=device,
        device_type=device_type,
        device_model=device_model,
        product_model=product_model,
    )

    # 5. First refresh (firmware version updated in coordinator)
    await coordinator.async_config_entry_first_refresh()

    # 6. Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Integration setup completed for %s", device.name)
    return True


async def _setup_api_with_error_handling(
    hass: HomeAssistant, entry: ConfigEntry, device_type: str
) -> Any:
    """Set up API with error handling."""
    _LOGGER.debug("Starting API setup")
    try:
        api = await _setup_api(hass, entry)
    except ConfigEntryAuthFailed:
        raise
    except (OSError, RuntimeError) as e:
        _LOGGER.error("Error during API setup: %s", e)
        raise ConfigEntryNotReady(f"API setup failed: {e}") from e
    else:
        _LOGGER.debug("API setup successful, device type: %s", device_type)
        return api


async def async_unload_entry(
    hass: HomeAssistant, entry: GrandstreamConfigEntry
) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
