"""The Growatt server PV inverter sensor integration."""

from collections.abc import Mapping
from json import JSONDecodeError
import logging

import growattServer
from requests import RequestException

from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CACHED_API_KEY,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_URL,
    DEPRECATED_URLS,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
    PLATFORMS,
)
from .coordinator import GrowattConfigEntry, GrowattCoordinator
from .models import GrowattRuntimeData
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Growatt Server component."""
    # Register services
    async_setup_services(hass)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> bool:
    """Migrate old config entries.

    Migration from version 1.0 to 1.1:
    - Resolves DEFAULT_PLANT_ID (legacy value "0") to actual plant_id
    - Only applies to Classic API (username/password authentication)
    - Caches the logged-in API instance to avoid growatt server API rate limiting

    Rate Limiting Workaround:
    The Growatt Classic API rate-limits individual endpoints (login, plant_list,
    device_list) with 5-minute windows. Without caching, the sequence would be:
        Migration: login() → plant_list()
        Setup:     login() → device_list()
    This results in 2 login() calls within seconds, triggering rate limits.

    By caching the API instance (which contains the authenticated session), we
    achieve:
        Migration: login() → plant_list() → [cache API instance]
        Setup:     [reuse cached API] → device_list()
    This reduces to just 1 login() call during the migration+setup cycle and prevent account lockout.
    """
    _LOGGER.debug(
        "Migrating config entry from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    # Migrate from version 1.0 to 1.1
    if config_entry.version == 1 and config_entry.minor_version < 1:
        config = config_entry.data

        # First, ensure auth_type field exists (legacy config entry migration)
        # This handles config entries created before auth_type was introduced
        if CONF_AUTH_TYPE not in config:
            new_data = dict(config_entry.data)
            # Detect auth type based on which fields are present
            if CONF_TOKEN in config:
                new_data[CONF_AUTH_TYPE] = AUTH_API_TOKEN
                hass.config_entries.async_update_entry(config_entry, data=new_data)
                config = config_entry.data
                _LOGGER.debug("Added auth_type field to V1 API config entry")
            elif CONF_USERNAME in config:
                new_data[CONF_AUTH_TYPE] = AUTH_PASSWORD
                hass.config_entries.async_update_entry(config_entry, data=new_data)
                config = config_entry.data
                _LOGGER.debug("Added auth_type field to Classic API config entry")
            else:
                # Config entry has no auth fields - this is invalid but migration
                # should still succeed. Setup will fail later with a clearer error.
                _LOGGER.warning(
                    "Config entry has no authentication fields. "
                    "Setup will fail until the integration is reconfigured"
                )

        # Handle DEFAULT_PLANT_ID resolution
        if config.get(CONF_PLANT_ID) == DEFAULT_PLANT_ID:
            # V1 API should never have DEFAULT_PLANT_ID (plant selection happens in config flow)
            # If it does, this indicates a corrupted config entry
            if config.get(CONF_AUTH_TYPE) == AUTH_API_TOKEN:
                _LOGGER.error(
                    "V1 API config entry has DEFAULT_PLANT_ID, which indicates a "
                    "corrupted configuration. Please reconfigure the integration"
                )
                return False

            # Classic API with DEFAULT_PLANT_ID - resolve to actual plant_id
            if config.get(CONF_AUTH_TYPE) == AUTH_PASSWORD:
                username = config.get(CONF_USERNAME)
                password = config.get(CONF_PASSWORD)
                url = config.get(CONF_URL, DEFAULT_URL)

                if not username or not password:
                    # Credentials missing - cannot migrate
                    _LOGGER.error(
                        "Cannot migrate DEFAULT_PLANT_ID due to missing credentials"
                    )
                    return False

                try:
                    # Create API instance and login
                    api, login_response = await _create_api_and_login(
                        hass, username, password, url
                    )

                    # Resolve DEFAULT_PLANT_ID to actual plant_id
                    plant_info = await hass.async_add_executor_job(
                        api.plant_list, login_response["user"]["id"]
                    )
                except (ConfigEntryError, RequestException, JSONDecodeError) as ex:
                    # API failure during migration - return False to retry later
                    _LOGGER.error(
                        "Failed to resolve plant_id during migration: %s. "
                        "Migration will retry on next restart",
                        ex,
                    )
                    return False

                if not plant_info or "data" not in plant_info or not plant_info["data"]:
                    _LOGGER.error(
                        "No plants found for this account. "
                        "Migration will retry on next restart"
                    )
                    return False

                first_plant_id = plant_info["data"][0]["plantId"]

                # Update config entry with resolved plant_id
                new_data = dict(config_entry.data)
                new_data[CONF_PLANT_ID] = first_plant_id
                hass.config_entries.async_update_entry(
                    config_entry, data=new_data, minor_version=1
                )

                # Cache the logged-in API instance for reuse in async_setup_entry()
                hass.data.setdefault(DOMAIN, {})
                hass.data[DOMAIN][f"{CACHED_API_KEY}{config_entry.entry_id}"] = api

                _LOGGER.info(
                    "Migrated config entry to use specific plant_id '%s'",
                    first_plant_id,
                )
        else:
            # No DEFAULT_PLANT_ID to resolve, just bump version
            hass.config_entries.async_update_entry(config_entry, minor_version=1)

        _LOGGER.debug("Migration completed to version %s.%s", config_entry.version, 1)

    return True


async def _create_api_and_login(
    hass: HomeAssistant, username: str, password: str, url: str
) -> tuple[growattServer.GrowattApi, dict]:
    """Create API instance and perform login.

    Returns both the API instance (with authenticated session) and the login
    response (containing user_id needed for subsequent API calls).

    """
    api = growattServer.GrowattApi(add_random_user_id=True, agent_identifier=username)
    api.server_url = url

    login_response = await hass.async_add_executor_job(
        _login_classic_api, api, username, password
    )

    return api, login_response


def _login_classic_api(
    api: growattServer.GrowattApi, username: str, password: str
) -> dict:
    """Log in to Classic API and return user info."""
    try:
        login_response = api.login(username, password)
    except (RequestException, JSONDecodeError) as ex:
        raise ConfigEntryError(
            f"Error communicating with Growatt API during login: {ex}"
        ) from ex

    if not login_response.get("success"):
        msg = login_response.get("msg", "Unknown error")
        _LOGGER.debug("Growatt login failed: %s", msg)
        if msg == LOGIN_INVALID_AUTH_CODE:
            raise ConfigEntryAuthFailed("Username, Password or URL may be incorrect!")
        raise ConfigEntryError(f"Growatt login failed: {msg}")

    return login_response


def get_device_list_v1(
    api, config: Mapping[str, str]
) -> tuple[list[dict[str, str]], str]:
    """Device list logic for Open API V1.

    Plant selection is handled in the config flow before this function is called.
    This function expects a specific plant_id and fetches devices for that plant.

    """
    plant_id = config[CONF_PLANT_ID]
    try:
        devices_dict = api.device_list(plant_id)
    except growattServer.GrowattV1ApiError as e:
        raise ConfigEntryError(
            f"API error during device list: {e} (Code: {getattr(e, 'error_code', None)}, Message: {getattr(e, 'error_msg', None)})"
        ) from e
    devices = devices_dict.get("devices", [])
    # Only MIN device (type = 7) support implemented in current V1 API
    supported_devices = [
        {
            "deviceSn": device.get("device_sn", ""),
            "deviceType": "min",
        }
        for device in devices
        if device.get("type") == 7
    ]

    for device in devices:
        if device.get("type") != 7:
            _LOGGER.warning(
                "Device %s with type %s not supported in Open API V1, skipping",
                device.get("device_sn", ""),
                device.get("type"),
            )
    return supported_devices, plant_id


async def async_setup_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> bool:
    """Set up Growatt from a config entry."""

    config = config_entry.data
    url = config.get(CONF_URL, DEFAULT_URL)

    # If the URL has been deprecated then change to the default instead
    if url in DEPRECATED_URLS:
        url = DEFAULT_URL
        new_data = dict(config_entry.data)
        new_data[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    # Determine API version and get devices
    # Note: auth_type field is guaranteed to exist after migration
    if config.get(CONF_AUTH_TYPE) == AUTH_API_TOKEN:
        # V1 API (token-based, no login needed)
        token = config[CONF_TOKEN]
        api = growattServer.OpenApiV1(token=token)
        devices, plant_id = await hass.async_add_executor_job(
            get_device_list_v1, api, config
        )
    elif config.get(CONF_AUTH_TYPE) == AUTH_PASSWORD:
        # Classic API (username/password with login)
        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]

        # Check if migration cached an authenticated API instance for us to reuse.
        # This avoids calling login() twice (once in migration, once here) which
        # would trigger rate limiting.
        cached_api = hass.data.get(DOMAIN, {}).pop(
            f"{CACHED_API_KEY}{config_entry.entry_id}", None
        )

        if cached_api:
            # Reuse the logged-in API instance from migration (rate limit optimization)
            api = cached_api
            _LOGGER.debug("Reusing logged-in session from migration")
        else:
            # No cached API (normal setup or migration didn't run)
            # Create new API instance and login
            api, _ = await _create_api_and_login(hass, username, password, url)

        # Get plant_id and devices using the authenticated session
        plant_id = config[CONF_PLANT_ID]
        try:
            devices = await hass.async_add_executor_job(api.device_list, plant_id)
        except (RequestException, JSONDecodeError) as ex:
            raise ConfigEntryError(
                f"Error communicating with Growatt API during device list: {ex}"
            ) from ex
    else:
        raise ConfigEntryError("Unknown authentication type in config entry.")

    # Create a coordinator for the total sensors
    total_coordinator = GrowattCoordinator(
        hass, config_entry, plant_id, "total", plant_id
    )

    # Create coordinators for each device
    device_coordinators = {
        device["deviceSn"]: GrowattCoordinator(
            hass, config_entry, device["deviceSn"], device["deviceType"], plant_id
        )
        for device in devices
        if device["deviceType"] in ["inverter", "tlx", "storage", "mix", "min"]
    }

    # Perform the first refresh for the total coordinator
    await total_coordinator.async_config_entry_first_refresh()

    # Perform the first refresh for each device coordinator
    for device_coordinator in device_coordinators.values():
        await device_coordinator.async_config_entry_first_refresh()

    # Store runtime data in the config entry
    config_entry.runtime_data = GrowattRuntimeData(
        total_coordinator=total_coordinator,
        devices=device_coordinators,
    )

    # Set up all the entities
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
