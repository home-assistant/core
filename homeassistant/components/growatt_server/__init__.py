"""The Growatt server PV inverter sensor integration.

This integration supports two distinct Growatt APIs with different auth models:

Classic API (username/password):
- Authenticates via api.login(), which returns a dict with a "success" key.
- Auth failure is signalled by success=False and msg="502" (LOGIN_INVALID_AUTH_CODE).
- A failed login does NOT raise an exception — the return value must be checked.
- Setup logs in once and all coordinators share that session. A coordinator
  logs in again only when a request comes back unauthenticated, and at most
  once per RELOGIN_INTERVAL. If the retry after a login still gets a web page,
  the update fails and a repair issue is raised.

Open API V1 (API token):
- Stateless — no login call, token is sent as a Bearer header on every request.
- Auth failure is signalled by raising GrowattV1ApiError with
  error_code=GrowattV1ApiErrorCode.NO_PRIVILEGE. The library NEVER returns a failure silently;
  any non-zero error_code raises an exception via _process_response().
- Because the library always raises on error, return-value validation after a
  successful V1 API call is unnecessary — if it returned, the token was valid.

Error handling pattern for reauth:
- Classic API: check NOT login_response["success"] and msg == LOGIN_INVALID_AUTH_CODE
  → raise ConfigEntryAuthFailed
- V1 API: catch GrowattV1ApiError with error_code == GrowattV1ApiErrorCode.NO_PRIVILEGE
  → raise ConfigEntryAuthFailed
- Classic API: msg == LOGIN_RATE_LIMITED_CODE (507, too many logins)
  → ConfigEntryNotReady (setup) or UpdateFailed (coordinator), both with
  retry_after so no login is attempted until the cooldown has passed
- All other errors → ConfigEntryError (setup) or UpdateFailed (coordinator)
"""

from collections.abc import Mapping
import datetime as dt
from json import JSONDecodeError
import logging

import growattServer
from growattServer import GrowattV1ApiErrorCode
from requests import RequestException

from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_URL,
    DEPRECATED_URLS,
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
    PLATFORMS,
    SUPPORTED_DEVICE_TYPES,
    V1_DEVICE_TYPES,
)
from .coordinator import (
    GrowattClassicSession,
    GrowattConfigEntry,
    GrowattCoordinator,
    GrowattLoginRateLimited,
)
from .models import GrowattRuntimeData
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Logged-in sessions by (server URL, username), so setup retries and the setup
# after migration reuse them instead of logging in again.
DATA_CLASSIC_SESSIONS: HassKey[dict[tuple[str, str], GrowattClassicSession]] = HassKey(
    "growatt_server_classic_sessions"
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Growatt Server integration."""
    # Register services
    async_setup_services(hass)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> None:
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
    This reduces to just 1 login() call during the
    migration+setup cycle and prevent account lockout.
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
            # V1 API should never have DEFAULT_PLANT_ID
            # (plant selection happens in config flow)
            # If it does, this indicates a corrupted config entry
            if config.get(CONF_AUTH_TYPE) == AUTH_API_TOKEN:
                raise ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="migration_invalid_plant_id",
                )

            # Classic API with DEFAULT_PLANT_ID - resolve to actual plant_id
            if config.get(CONF_AUTH_TYPE) == AUTH_PASSWORD:
                username = config.get(CONF_USERNAME)
                password = config.get(CONF_PASSWORD)
                url = _server_url(config)

                if not username or not password:
                    raise ConfigEntryError(
                        translation_domain=DOMAIN,
                        translation_key="migration_missing_credentials",
                    )

                try:
                    # Create API instance and login
                    session, login_response = await _create_api_and_login(
                        hass, username, password, url
                    )

                    # Resolve DEFAULT_PLANT_ID to actual plant_id
                    plant_info = await hass.async_add_executor_job(
                        session.api.plant_list, login_response["user"]["id"]
                    )
                except (ConfigEntryError, RequestException, JSONDecodeError) as ex:
                    raise ConfigEntryNotReady(
                        translation_domain=DOMAIN,
                        translation_key="migration_plant_id_failed",
                    ) from ex

                # plant_list() is annotated as list, but the classic API returns
                # {"data": [...]}. Remove once the annotation is fixed upstream:
                # https://github.com/indykoning/PyPi_GrowattServer/issues/157
                if not isinstance(plant_info, dict) or not plant_info.get("data"):
                    raise ConfigEntryError(
                        translation_domain=DOMAIN,
                        translation_key="migration_no_plants",
                        translation_placeholders={"username": username},
                    )

                first_plant_id = plant_info["data"][0]["plantId"]

                # Update config entry with resolved plant_id
                new_data = dict(config_entry.data)
                new_data[CONF_PLANT_ID] = first_plant_id
                hass.config_entries.async_update_entry(
                    config_entry, data=new_data, minor_version=1
                )

                _LOGGER.info(
                    "Migrated config entry to use specific plant_id '%s'",
                    first_plant_id,
                )
        else:
            # No DEFAULT_PLANT_ID to resolve, just bump version
            hass.config_entries.async_update_entry(config_entry, minor_version=1)

        _LOGGER.debug("Migration completed to version %s.%s", config_entry.version, 1)


def _server_url(config: Mapping[str, str]) -> str:
    """Return the configured server URL, with deprecated ones replaced."""
    url = config.get(CONF_URL, DEFAULT_URL)
    return DEFAULT_URL if url in DEPRECATED_URLS else url


async def _create_api_and_login(
    hass: HomeAssistant, username: str, password: str, url: str
) -> tuple[GrowattClassicSession, dict]:
    """Create API instance and perform login.

    Returns both the session (with the authenticated API instance) and the login
    response (containing user_id needed for subsequent API calls).

    """
    api = growattServer.GrowattApi(add_random_user_id=True, agent_identifier=username)
    api.server_url = url
    session = GrowattClassicSession(hass, api, username, password)

    login_response = await hass.async_add_executor_job(_login_classic_api, session)
    hass.data.setdefault(DATA_CLASSIC_SESSIONS, {})[session.account] = session

    return session, login_response


def _login_classic_api(session: GrowattClassicSession) -> dict:
    """Log in to Classic API and return user info."""
    try:
        login_response = session.login()
    except (RequestException, JSONDecodeError) as ex:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(ex)},
        ) from ex
    except GrowattLoginRateLimited as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="login_rate_limited",
            retry_after=ex.retry_after,
        ) from ex

    if not login_response.get("success"):
        msg = login_response.get("msg", "Unknown error")
        _LOGGER.debug("Growatt login failed: %s", msg)
        if msg == LOGIN_INVALID_AUTH_CODE:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_credentials",
            )
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="login_failed",
            translation_placeholders={"message": msg},
        )

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
        if e.error_code == GrowattV1ApiErrorCode.NO_PRIVILEGE:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": e.error_msg or str(e)},
            ) from e
        if e.error_code == GrowattV1ApiErrorCode.RATE_LIMITED:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                translation_placeholders={"error": e.error_msg or str(e)},
            ) from e
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="api_error_with_code",
            translation_placeholders={
                "error": e.error_msg or str(e),
                "code": str(e.error_code),
            },
        ) from e
    devices = devices_dict.get("devices", [])
    supported_devices = [
        {
            "deviceSn": device.get("device_sn", ""),
            "deviceType": V1_DEVICE_TYPES[device.get("type")],
        }
        for device in devices
        if device.get("type") in V1_DEVICE_TYPES
    ]

    for device in devices:
        if device.get("type") not in V1_DEVICE_TYPES:
            _LOGGER.warning(
                "Device %s with type %s not supported in Open API V1, skipping",
                device.get("device_sn", ""),
                device.get("type"),
            )
    return supported_devices, plant_id


async def async_setup_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> None:
    """Set up Growatt from a config entry."""

    config = config_entry.data
    url = _server_url(config)

    if url != config.get(CONF_URL, DEFAULT_URL):
        new_data = dict(config_entry.data)
        new_data[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    # Determine API version and get devices
    # Note: auth_type field is guaranteed to exist after migration
    api: growattServer.GrowattApi
    classic_session: GrowattClassicSession | None = None
    if config.get(CONF_AUTH_TYPE) == AUTH_API_TOKEN:
        # V1 API (token-based, no login needed)
        token = config[CONF_TOKEN]
        api = growattServer.OpenApiV1(token=token)
        api.server_url = url
        devices, plant_id = await hass.async_add_executor_job(
            get_device_list_v1, api, config
        )
    elif config.get(CONF_AUTH_TYPE) == AUTH_PASSWORD:
        # Classic API (username/password with login)
        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]

        # Reuse the session from migration or an earlier setup attempt, so
        # neither costs another login.
        cached_session = hass.data.get(DATA_CLASSIC_SESSIONS, {}).get((url, username))
        if cached_session is not None and cached_session.password == password:
            classic_session = cached_session
            _LOGGER.debug("Reusing logged-in Growatt session")
        else:
            classic_session, _ = await _create_api_and_login(
                hass, username, password, url
            )
        api = classic_session.api
        plant_id = config[CONF_PLANT_ID]
    else:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unknown_auth_type",
        )

    # Create a coordinator for the total sensors
    total_coordinator = GrowattCoordinator(
        hass, config_entry, plant_id, "total", plant_id, api, classic_session
    )

    if classic_session is not None:
        # Fetch the device list in the first refresh, so an expired session or
        # a web page gets the same renewal and repair handling as a poll.
        total_coordinator.request_device_list_scan()
    await total_coordinator.async_config_entry_first_refresh()
    if classic_session is not None:
        if total_coordinator.device_list is None:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_list_failed",
            )
        devices = total_coordinator.device_list

    # Create coordinators for each device
    device_coordinators = {
        device["deviceSn"]: GrowattCoordinator(
            hass,
            config_entry,
            device["deviceSn"],
            device["deviceType"],
            plant_id,
            api,
            classic_session,
        )
        for device in devices
        if device["deviceType"] in SUPPORTED_DEVICE_TYPES
    }

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

    async def _async_scan_for_new_devices(_now: dt.datetime) -> None:
        """Scan for new or removed devices and update HA accordingly."""
        # Fetch current config (in case it was updated via reauth or options)
        current_plant_id = config_entry.data[CONF_PLANT_ID]

        total_coordinator = config_entry.runtime_data.total_coordinator
        # Signal the coordinator to also fetch the device list on its next
        # _sync_update_data run, then force an immediate refresh, so the
        # device_list call runs in the same executor job as the plant overview.
        total_coordinator.request_device_list_scan()
        await total_coordinator.async_refresh()

        if not total_coordinator.last_update_success:
            _LOGGER.debug("Coordinator refresh failed during device scan, skipping")
            return

        current_devices = total_coordinator.device_list
        if current_devices is None:
            _LOGGER.debug(
                "Device list not populated after coordinator refresh, skipping scan"
            )
            return

        runtime_data = config_entry.runtime_data
        current_device_sns = {device["deviceSn"] for device in current_devices}

        # Remove stale devices
        device_registry = dr.async_get(hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            device_domain_ids = {
                identifier[1]
                for identifier in device_entry.identifiers
                if identifier[0] == DOMAIN
            }
            if not device_domain_ids:
                continue
            # Skip the plant "total" device
            if current_plant_id in device_domain_ids:
                continue
            if device_domain_ids.isdisjoint(current_device_sns):
                for device_sn in device_domain_ids:
                    if coordinator := runtime_data.devices.pop(device_sn, None):
                        await coordinator.async_shutdown()
                device_registry.async_remove_device(device_entry.id)

        # Add new devices
        new_coordinators: list[GrowattCoordinator] = []
        for device in current_devices:
            device_sn = device["deviceSn"]
            device_type = device["deviceType"]
            if device_sn in runtime_data.devices:
                continue
            if device_type not in SUPPORTED_DEVICE_TYPES:
                _LOGGER.debug(
                    "New device %s with type %s is not supported, skipping",
                    device_sn,
                    device_type,
                )
                continue
            coordinator = GrowattCoordinator(
                hass,
                config_entry,
                device_sn,
                device_type,
                current_plant_id,
                api,
                classic_session,
            )
            await coordinator.async_refresh()
            if not coordinator.last_update_success:
                _LOGGER.debug("Failed to refresh new device %s, skipping", device_sn)
                await coordinator.async_shutdown()
                continue
            runtime_data.devices[device_sn] = coordinator
            new_coordinators.append(coordinator)

        if new_coordinators:
            async_dispatcher_send(
                hass,
                f"{DOMAIN}_new_device_{config_entry.entry_id}",
                new_coordinators,
            )

    config_entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_for_new_devices, DEVICE_SCAN_INTERVAL
        )
    )


async def async_unload_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
    # A reload or reauth starts from a fresh login.
    if config_entry.data.get(CONF_AUTH_TYPE) == AUTH_PASSWORD:
        hass.data.get(DATA_CLASSIC_SESSIONS, {}).pop(
            (_server_url(config_entry.data), config_entry.data[CONF_USERNAME]), None
        )
