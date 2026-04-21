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
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
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
    # Initialize domain data early to allow safe cleanup even if setup fails
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = None

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

    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed from err
    except OAuth2TokenRequestError as err:
        raise ConfigEntryNotReady from err
    except ValueError as err:
        _LOGGER.error(
            "OAuth2 token validation failed: %s. "
            "The refresh token may have expired. Please re-authenticate",
            err,
        )
        raise ConfigEntryAuthFailed("Token expired") from err

    api_client = HeimanApiClient(hass=hass, session=session)

    device_management = DeviceManagement()
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
    area_sync_mode = entry.data.get(CONF_AREA_NAME_RULE, AREA_NAME_RULE_HOME_ROOM)
    device_management.configure(
        filter_config=filter_config,
        area_sync_mode=area_sync_mode,
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=api_client,
        config_entry=entry,
        device_management=device_management,
        oauth_session=session,
    )

    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_init_mqtt_client()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register service only once (when first entry is loaded)
    if not hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES):

        async def handle_read_device_properties(call):
            """Handle read device properties service call."""
            device_registry_ids = call.data.get("device_id")
            if not device_registry_ids:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="device_id_required",
                )

            # Normalize to iterable (handle str, list, set, tuple)
            if isinstance(device_registry_ids, str):
                device_registry_ids = (device_registry_ids,)
            elif not isinstance(device_registry_ids, (list, set, tuple)):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_device_id_type",
                    translation_placeholders={
                        "type": type(device_registry_ids).__name__
                    },
                )

            # Get device registry to translate device registry IDs to Heiman device_ids
            device_registry = dr.async_get(hass)

            for device_registry_id in device_registry_ids:
                device_entry = device_registry.async_get(device_registry_id)
                if not device_entry:
                    _LOGGER.error(
                        "Device %s not found in device registry", device_registry_id
                    )
                    continue

                # Extract Heiman device_id from device identifiers
                heiman_device_id = None
                for identifier in device_entry.identifiers:
                    if identifier[0] == DOMAIN:
                        heiman_device_id = identifier[1]
                        break

                if not heiman_device_id:
                    _LOGGER.error(
                        "Device %s does not have a valid Heiman device identifier",
                        device_registry_id,
                    )
                    continue

                # Try all coordinators until we find the device
                for coordinator in hass.data.get(DOMAIN, {}).values():
                    if coordinator is None:
                        continue
                    # Check if device exists in this coordinator before calling
                    if coordinator.get_device(heiman_device_id):
                        await coordinator.async_read_device_properties(heiman_device_id)
                        # Device found and handled, continue with next selected device
                        break
                else:
                    _LOGGER.warning(
                        "Heiman device %s not found in any coordinator",
                        heiman_device_id,
                    )

        hass.services.async_register(
            DOMAIN,
            SERVICE_READ_DEVICE_PROPERTIES,
            handle_read_device_properties,
        )

    return True


async def _async_call_cleanup_method(
    target: object, method_names: tuple[str, ...]
) -> None:
    """Call the first available cleanup method on a target."""
    for method_name in method_names:
        method = getattr(target, method_name, None)
        if method is None:
            continue
        result = method()
        if hasattr(result, "__await__"):
            await result
        return


async def async_unload_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        domain_data = hass.data.get(DOMAIN)
        if domain_data is not None:
            domain_data.pop(entry.entry_id, None)
            if not domain_data:
                hass.data.pop(DOMAIN, None)
                if hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES):
                    hass.services.async_remove(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)
        return True

    # Disconnect MQTT client
    mqtt_client = getattr(coordinator, "mqtt_client", None)
    if mqtt_client is not None:
        try:
            await _async_call_cleanup_method(
                mqtt_client,
                (
                    "async_disconnect",
                    "disconnect",
                ),
            )
        except Exception:
            _LOGGER.exception("Error disconnecting MQTT client during unload")

    # Close API client
    api_client = getattr(coordinator, "api_client", None)
    if api_client is not None:
        try:
            await _async_call_cleanup_method(
                api_client,
                (
                    "async_close",
                    "close",
                ),
            )
        except Exception:
            _LOGGER.exception("Error closing API client during unload")

    # Remove coordinator from hass.data
    domain_data = hass.data.get(DOMAIN)
    if domain_data is not None:
        domain_data.pop(entry.entry_id, None)

        # If this was the last entry, remove the service and clean up hass.data
        if not domain_data:
            hass.data.pop(DOMAIN, None)
            if hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES):
                hass.services.async_remove(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Migrate old configuration entries."""

    return True
