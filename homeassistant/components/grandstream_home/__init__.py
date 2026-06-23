"""The Grandstream Home integration."""

from dataclasses import dataclass
import logging

from grandstream_home_api import (
    GDSPhoneAPI,
    GNSNasAPI,
    attempt_login,
    create_api_instance,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import GrandstreamConfigEntry, GrandstreamCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@dataclass
class GrandstreamRuntimeData:
    """Runtime data for Grandstream config entry."""

    api: GDSPhoneAPI | GNSNasAPI
    coordinator: GrandstreamCoordinator
    device_info: DeviceInfo
    device_model: str
    product_model: str | None
    unique_id: str


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
    mac_address: str | None,
    firmware_version: str | None,
) -> DeviceInfo:
    """Create device info for Home Assistant."""
    display_model = _get_display_model(device_model, product_model)

    connections: set[tuple[str, str]] = set()
    if mac_address:
        connections.add((dr.CONNECTION_NETWORK_MAC, mac_address))

    return DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer="Grandstream",
        model=display_model,
        suggested_area="Entry",
        sw_version=firmware_version,
        connections=connections,
    )


async def _setup_api(
    hass: HomeAssistant, entry: ConfigEntry
) -> GDSPhoneAPI | GNSNasAPI:
    """Set up and initialize API with error handling."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    port = entry.data[CONF_PORT]
    verify_ssl = entry.data[CONF_VERIFY_SSL]
    device_model = entry.data[CONF_TYPE]

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
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="api_setup_failed",
            translation_placeholders={"error": str(e)},
        ) from e

    if success:
        return api

    if error_type == "offline":
        _LOGGER.debug("Device is offline or unreachable")
        return api

    if error_type == "ha_control_disabled":
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="ha_control_disabled",
        )

    if error_type == "account_locked":
        _LOGGER.debug("Account is temporarily locked, integration will retry later")
        return api

    raise ConfigEntryNotReady(
        translation_domain=DOMAIN,
        translation_key="invalid_auth",
    )


async def async_setup_entry(hass: HomeAssistant, entry: GrandstreamConfigEntry) -> bool:
    """Set up Grandstream Home integration."""
    _LOGGER.debug("Starting integration initialization: %s", entry.entry_id)

    # Extract device info from entry
    device_model = entry.data[CONF_TYPE]
    product_model = entry.data.get(CONF_MODEL)

    # 1. Set up API
    api = await _setup_api(hass, entry)

    # 2. unique_id is always set in config flow
    assert entry.unique_id is not None

    # 3. Create device info
    mac_address = api.device_mac
    discovery_version = entry.data.get(ATTR_SW_VERSION)

    device_info = _create_device_info(
        entry=entry,
        unique_id=entry.unique_id,
        device_model=device_model,
        product_model=product_model,
        mac_address=mac_address,
        firmware_version=discovery_version,
    )

    # 4. Create coordinator (pass api and discovery_version for firmware fallback)
    coordinator = GrandstreamCoordinator(hass, entry, api, discovery_version)

    # 5. Store runtime data BEFORE first refresh
    entry.runtime_data = GrandstreamRuntimeData(
        api=api,
        coordinator=coordinator,
        device_info=device_info,
        device_model=device_model,
        product_model=product_model,
        unique_id=entry.unique_id,
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
