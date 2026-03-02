"""The Eufy Security integration."""

from __future__ import annotations

import logging

from eufy_security import (
    CannotConnectError,
    CaptchaRequiredError,
    EufySecurityAPI,
    EufySecurityError,
    InvalidCredentialsError,
)

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CONFIG_ENTRY_MINOR_VERSION,
    CONF_RTSP_CREDENTIALS,
    CONF_SESSION_STATE,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import (
    EufySecurityConfigEntry,
    EufySecurityCoordinator,
    EufySecurityData,
)

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: EufySecurityConfigEntry
) -> bool:
    """Migrate old config entry data to new format."""
    if config_entry.version == 1 and config_entry.minor_version < 2:
        # Migrate from individual keys to session_state dict
        data = dict(config_entry.data)
        session_state: dict[str, str | None] = {}
        for key in (
            "token",
            "token_expiration",
            "api_base",
            "private_key",
            "server_public_key",
        ):
            if key in data:
                session_state[key] = data.pop(key)
        if session_state:
            data[CONF_SESSION_STATE] = session_state
        hass.config_entries.async_update_entry(
            config_entry, data=data, minor_version=CONF_CONFIG_ENTRY_MINOR_VERSION
        )
        _LOGGER.debug("Migrated config entry to version 1.2")

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: EufySecurityConfigEntry
) -> bool:
    """Set up Eufy Security from a config entry."""
    session = async_get_clientsession(hass)

    # Create API instance
    api = EufySecurityAPI(
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        session,
    )

    # Try to restore previous session from config entry data
    needs_auth = True
    session_state = entry.data.get(CONF_SESSION_STATE, {})
    if session_state and api.restore_session(session_state):
        # Test if the restored session still works
        try:
            await api.async_update_device_info()
            needs_auth = False
            _LOGGER.debug("Restored session is valid")
        except EufySecurityError:
            _LOGGER.debug("Restored session invalid, will re-authenticate")

    if needs_auth:
        # Authenticate and get device info in one try/catch block
        try:
            _LOGGER.debug("Authenticating with API")
            await api.async_authenticate()
            await api.async_update_device_info()
        except CaptchaRequiredError as err:
            # CAPTCHA required - trigger reauth flow so user can solve it
            _LOGGER.warning("CAPTCHA required, triggering reauthentication")
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except CannotConnectError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except EufySecurityError as err:
            _LOGGER.warning("API error during auth: %s", err)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    # Persist the latest session state so refreshed tokens/keys survive restarts
    new_data = dict(entry.data)
    new_data[CONF_SESSION_STATE] = api.get_session_state()
    hass.config_entries.async_update_entry(entry, data=new_data)
    coordinator = EufySecurityCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    # Set per-camera RTSP credentials from options
    rtsp_credentials = entry.options.get(CONF_RTSP_CREDENTIALS, {})
    _LOGGER.debug("RTSP credentials from options: %s", list(rtsp_credentials.keys()))
    for serial, camera in api.cameras.items():
        camera_creds = rtsp_credentials.get(serial, {})
        camera.rtsp_username = camera_creds.get("username")
        camera.rtsp_password = camera_creds.get("password")
        _LOGGER.debug(
            "Camera %s (%s): RTSP credentials configured: %s",
            camera.name,
            serial,
            "yes" if camera.rtsp_username or camera.rtsp_password else "no",
        )

    devices = {
        "cameras": {camera.serial: camera for camera in api.cameras.values()},
        "stations": {station.serial: station for station in api.stations.values()},
    }

    entry.runtime_data = EufySecurityData(
        api=api,
        devices=devices,
        coordinator=coordinator,
    )

    def _update_devices_from_api() -> None:
        """Keep runtime devices snapshot in sync with API device lists."""
        devices["cameras"] = {camera.serial: camera for camera in api.cameras.values()}
        devices["stations"] = {
            station.serial: station for station in api.stations.values()
        }

    # Keep runtime device mapping in sync whenever the coordinator refreshes
    remove_listener = coordinator.async_add_listener(_update_devices_from_api)
    entry.async_on_unload(remove_listener)

    # Ensure the snapshot is up to date after initial refresh
    _update_devices_from_api()
    # Reload entry when options change (RTSP credentials)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: EufySecurityConfigEntry
) -> None:
    """Handle options update - reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: EufySecurityConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: EufySecurityConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a config entry from a device.

    Allow removal of stale devices that are no longer present in the Eufy account.
    """
    # Get current device serials from runtime data
    current_serials: set[str] = set()
    runtime_data = getattr(config_entry, "runtime_data", None)
    if runtime_data:
        cameras = runtime_data.devices.get("cameras", {})
        stations = runtime_data.devices.get("stations", {})
        current_serials.update(cameras.keys())
        current_serials.update(stations.keys())

    # Check if the device is still present
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN and identifier[1] in current_serials:
            # Device is still present, don't allow removal
            return False

    # Device is no longer present in the account, allow removal
    return True
