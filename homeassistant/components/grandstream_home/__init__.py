"""The Grandstream Home integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from grandstream_home_api import (
    DEFAULT_PORT,
    GDSPhoneAPI,
    attempt_login,
    create_api_instance,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo, format_mac

from .const import (
    CONF_DEVICE_MODEL,
    CONF_FIRMWARE_VERSION,
    CONF_PRODUCT_MODEL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import GrandstreamCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@dataclass
class GrandstreamRuntimeData:
    """Runtime data for Grandstream config entry."""

    api: GDSPhoneAPI
    coordinator: GrandstreamCoordinator
    device_info: DeviceInfo
    device_model: str
    product_model: str | None
    unique_id: str


type GrandstreamConfigEntry = ConfigEntry[GrandstreamRuntimeData]


def _get_display_model(device_model: str, product_model: str | None) -> str:
    """Get the model string to display in device info."""
    if product_model:
        return product_model
    return device_model


def _create_device_info(
    entry: ConfigEntry,
    unique_id: str,
    device_model: str,
    product_model: str | None,
    ip_address: str | None,
    mac_address: str | None,
    firmware_version: str | None,
) -> DeviceInfo:
    """Create device info for Home Assistant."""
    display_model = _get_display_model(device_model, product_model)
    model_info = display_model
    if ip_address:
        model_info = f"{display_model} (IP: {ip_address})"

    connections: set[tuple[str, str]] = set()
    if mac_address:
        connections.add(("mac", format_mac(mac_address)))

    return DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        name=entry.data.get("name", "Grandstream Device"),
        manufacturer="Grandstream",
        model=model_info,
        suggested_area="Entry",
        sw_version=firmware_version or "unknown",
        connections=connections,
    )


async def _setup_api(hass: HomeAssistant, entry: ConfigEntry) -> GDSPhoneAPI:
    """Set up and initialize API with error handling."""
    host = entry.data.get("host", "")
    username = entry.data.get(CONF_USERNAME, "")
    password = entry.data.get(CONF_PASSWORD, "")
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)
    device_model = entry.data[CONF_DEVICE_MODEL]

    # Create API instance using library function
    api = create_api_instance(
        device_type=device_model,
        host=host,
        username=username,
        password=password,
        port=port,
        verify_ssl=verify_ssl,
    )

    # Initialize API connection (authenticate and establish session)
    try:
        success, error_type = await hass.async_add_executor_job(attempt_login, api)
    except (OSError, RuntimeError) as e:
        _LOGGER.error("Error during API setup: %s", e)
        raise ConfigEntryNotReady(f"API setup failed: {e}") from e

    if success:
        return api  # type: ignore[return-value]

    if error_type == "offline":
        _LOGGER.debug("Device is offline or unreachable")
        return api  # type: ignore[return-value]

    if error_type == "ha_control_disabled":
        raise ConfigEntryNotReady(
            "Home Assistant control is disabled on the device. "
            "Please enable it in the device web interface."
        )

    if error_type == "account_locked":
        _LOGGER.debug("Account is temporarily locked, integration will retry later")
        return api  # type: ignore[return-value]

    # Authentication failed - convert to NotReady to avoid reauth flow
    _LOGGER.warning(
        "Authentication failed for %s. "
        "Please check credentials in the integration configuration",
        entry.data.get("name", "Unknown device"),
    )
    raise ConfigEntryNotReady("Authentication failed - invalid credentials")


async def async_setup_entry(hass: HomeAssistant, entry: GrandstreamConfigEntry) -> bool:
    """Set up Grandstream Home integration."""
    _LOGGER.debug("Starting integration initialization: %s", entry.entry_id)

    # Extract device info from entry
    device_model = entry.data[CONF_DEVICE_MODEL]
    product_model = entry.data.get(CONF_PRODUCT_MODEL)

    # 1. Set up API
    api = await _setup_api(hass, entry)

    # 2. Use entry unique_id or fallback to host-based ID
    unique_id = entry.unique_id or f"{device_model}_{entry.data.get('host', '')}"

    # 3. Create device info
    ip_address = api.host if api and api.host else entry.data.get("host")
    mac_address = api.device_mac if api and api.device_mac else None
    discovery_version = entry.data.get(CONF_FIRMWARE_VERSION)

    device_info = _create_device_info(
        entry=entry,
        unique_id=unique_id,
        device_model=device_model,
        product_model=product_model,
        ip_address=ip_address,
        mac_address=mac_address,
        firmware_version=discovery_version,
    )

    # 4. Create coordinator (pass api, unique_id and discovery_version for firmware fallback)
    coordinator = GrandstreamCoordinator(hass, entry, api, unique_id, discovery_version)

    # 5. Store runtime data BEFORE first refresh
    entry.runtime_data = GrandstreamRuntimeData(
        api=api,
        coordinator=coordinator,
        device_info=device_info,
        device_model=device_model,
        product_model=product_model,
        unique_id=unique_id,
    )

    # 6. First refresh (firmware version updated in coordinator)
    await coordinator.async_config_entry_first_refresh()

    # 7. Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Integration setup completed for %s", entry.title)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GrandstreamConfigEntry
) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
