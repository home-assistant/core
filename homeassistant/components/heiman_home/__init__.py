"""Heiman Home Assistant integration."""

from __future__ import annotations

import logging

from heimanconnect import DeviceManagement

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import HeimanApiClient
from .const import (
    AREA_NAME_RULE_HOME_ROOM,
    CONF_AREA_NAME_RULE,
    CONF_DEVICE_FILTER,
    CONF_DEVICE_FILTER_MODE,
    CONF_DEVICE_LIST,
    CONF_MODEL_FILTER_MODE,
    CONF_MODEL_LIST,
    CONF_ROOM_FILTER_MODE,
    CONF_ROOM_LIST,
    CONF_STATISTICS_LOGIC,
    CONF_TYPE_FILTER_MODE,
    CONF_TYPE_LIST,
    DOMAIN,
    PLATFORMS,
    SERVICE_READ_DEVICE_PROPERTIES,
)
from .coordinator import HeimanDataUpdateCoordinator

type HeimanConfigEntry = ConfigEntry[HeimanDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Set up Heiman from a config entry."""
    # Check if config contains token
    if CONF_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed("Config entry missing token")

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = OAuth2Session(hass, entry, implementation)

    # Validate token
    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed from err
    except OAuth2TokenRequestError as err:
        raise ConfigEntryNotReady from err
    except ValueError as err:
        # Handle empty response or invalid token format
        _LOGGER.error(
            "OAuth2 token validation failed: %s. "
            "The refresh token may have expired. Please re-authenticate",
            err,
        )
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="token_expired",
        ) from err

    # Create API client
    api_client = HeimanApiClient(hass=hass, session=session)

    # Test API connection
    try:
        await api_client.async_get_user_info()
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Heiman API: {err}") from err

    # Initialize device management
    device_management = DeviceManagement()

    # Configure device filtering
    filter_config = {
        "filter_mode": entry.data.get(CONF_DEVICE_FILTER, "exclude"),
        "statistics_logic": entry.data.get(CONF_STATISTICS_LOGIC, "or"),
        "room_filter_mode": entry.data.get(CONF_ROOM_FILTER_MODE, "exclude"),
        "room_list": entry.data.get(CONF_ROOM_LIST, []),
        "type_filter_mode": entry.data.get(CONF_TYPE_FILTER_MODE, "exclude"),
        "type_list": entry.data.get(CONF_TYPE_LIST, []),
        "model_filter_mode": entry.data.get(CONF_MODEL_FILTER_MODE, "exclude"),
        "model_list": entry.data.get(CONF_MODEL_LIST, []),
        "device_filter_mode": entry.data.get(CONF_DEVICE_FILTER_MODE, "exclude"),
        "device_list": entry.data.get(CONF_DEVICE_LIST, []),
    }

    # Configure area sync
    area_sync_mode = entry.data.get(CONF_AREA_NAME_RULE, AREA_NAME_RULE_HOME_ROOM)

    device_management.configure(
        filter_config=filter_config,
        area_sync_mode=area_sync_mode,
    )

    # Create data coordinator
    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=api_client,
        config_entry=entry,
        device_management=device_management,
        oauth_session=session,  # Pass OAuth2 session for MQTT token retrieval
    )

    # First data update
    await coordinator.async_config_entry_first_refresh()

    # Initialize MQTT client (for real-time device property updates)
    await coordinator.async_init_mqtt_client()

    # Store coordinator in hass.data and runtime_data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    # Load platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register service to read device properties
    async def handle_read_device_properties(call):
        """Handle read device properties service call."""
        device_id = call.data.get("device_id")
        if not device_id:
            _LOGGER.error("Device ID is required for read_device_properties service")
            return

        coordinator: HeimanDataUpdateCoordinator = entry.runtime_data
        await coordinator.async_read_device_properties(device_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        handle_read_device_properties,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Migrate old configuration entries."""

    return True
