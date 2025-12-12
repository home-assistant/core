"""The Eufy Security integration."""

from __future__ import annotations

import contextlib
from datetime import datetime
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
    CONF_API_BASE,
    CONF_PRIVATE_KEY,
    CONF_SERVER_PUBLIC_KEY,
    CONF_TOKEN,
    CONF_TOKEN_EXPIRATION,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import (
    EufySecurityConfigEntry,
    EufySecurityCoordinator,
    EufySecurityData,
)

_LOGGER = logging.getLogger(__name__)


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

    # Try to restore crypto state from config entry to avoid re-authentication
    needs_auth = True
    private_key = entry.data.get(CONF_PRIVATE_KEY)
    server_public_key = entry.data.get(CONF_SERVER_PUBLIC_KEY)
    token = entry.data.get(CONF_TOKEN)
    token_exp_str = entry.data.get(CONF_TOKEN_EXPIRATION)
    api_base = entry.data.get(CONF_API_BASE)

    if private_key and server_public_key and token:
        # Try to restore the crypto state
        if api.restore_crypto_state(private_key, server_public_key):
            # Parse token expiration
            token_exp = None
            if token_exp_str:
                with contextlib.suppress(ValueError):
                    token_exp = datetime.fromisoformat(token_exp_str)

            # Check if token is still valid
            if token_exp is None or datetime.now() < token_exp:
                api.set_token(token, token_exp, api_base)
                _LOGGER.debug("Restored Eufy Security session from stored crypto state")

                # Test if the restored session works
                try:
                    await api.async_update_device_info()
                    needs_auth = False
                    _LOGGER.debug("Restored session is valid")
                except (
                    InvalidCredentialsError,
                    CaptchaRequiredError,
                    EufySecurityError,
                ):
                    _LOGGER.debug("Restored session invalid, will re-authenticate")
            else:
                _LOGGER.debug("Token expired, will re-authenticate")
        else:
            _LOGGER.debug("Could not restore crypto state, will re-authenticate")

    if needs_auth:
        # Authenticate to get fresh ECDH encryption keys
        # (The v2 API uses encrypted responses that require session-specific keys)
        try:
            _LOGGER.debug("Authenticating with Eufy Security API")
            await api.async_authenticate()
        except CaptchaRequiredError as err:
            # CAPTCHA required - trigger reauth flow so user can solve it
            _LOGGER.warning(
                "CAPTCHA required for Eufy Security, triggering reauthentication"
            )
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
            _LOGGER.warning("Eufy Security API error during auth: %s", err)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        # Get device info with the authenticated session
        try:
            await api.async_update_device_info()
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except CaptchaRequiredError as err:
            # Token expired/invalid and CAPTCHA is required - trigger reauth
            _LOGGER.warning("CAPTCHA required, triggering reauthentication")
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
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    coordinator = EufySecurityCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    # Set per-camera RTSP credentials from options
    rtsp_credentials = entry.options.get("rtsp_credentials", {})
    _LOGGER.debug("RTSP credentials from options: %s", list(rtsp_credentials.keys()))
    for serial, camera in api.cameras.items():
        camera_creds = rtsp_credentials.get(serial, {})
        camera.rtsp_username = camera_creds.get("username")
        camera.rtsp_password = camera_creds.get("password")
        _LOGGER.debug(
            "Camera %s (%s): IP=%s, RTSP user=%s, RTSP pass=%s",
            camera.name,
            serial,
            camera.ip_address,
            camera.rtsp_username or "NOT SET",
            "SET" if camera.rtsp_password else "NOT SET",
        )

    entry.runtime_data = EufySecurityData(
        api=api,
        devices={
            "cameras": {camera.serial: camera for camera in api.cameras.values()},
            "stations": {station.serial: station for station in api.stations.values()},
        },
        coordinator=coordinator,
    )

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
