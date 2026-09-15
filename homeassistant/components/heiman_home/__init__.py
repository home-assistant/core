"""Heiman Home Assistant integration."""

import contextlib
import logging

from heimanconnect import DeviceManagement

from homeassistant.config_entries import ConfigEntry
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
from .const import PLATFORMS
from .coordinator import HeimanDataUpdateCoordinator, _async_call_cleanup_method

type HeimanConfigEntry = ConfigEntry[HeimanDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Set up Heiman from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady("OAuth2 implementation unavailable") from err

    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed(
            "OAuth2 authentication failed, re-authentication required"
        ) from err
    except OAuth2TokenRequestError as err:
        raise ConfigEntryNotReady(f"OAuth2 token request failed: {err}") from err
    except ValueError as err:
        _LOGGER.error(
            "OAuth2 token validation failed: %s. "
            "The refresh token may have expired. Please re-authenticate",
            err,
        )
        raise ConfigEntryAuthFailed("Token expired") from err

    api_client = HeimanApiClient(hass=hass, session=session)

    # Create device management (configuration is handled by coordinator)
    device_management = DeviceManagement()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=api_client,
        config_entry=entry,
        device_management=device_management,
        oauth_session=session,
    )

    try:
        await coordinator.async_config_entry_first_refresh()

        # Initialize MQTT client after successful first refresh
        await coordinator.async_init_mqtt_client()
    except Exception:
        # Clean up resources if first refresh or MQTT initialization fails
        mqtt_client = getattr(coordinator, "mqtt_client", None)
        if mqtt_client is not None:
            with contextlib.suppress(Exception):
                await _async_call_cleanup_method(
                    mqtt_client,
                    (
                        "async_disconnect",
                        "disconnect",
                    ),
                )
        with contextlib.suppress(Exception):
            await _async_call_cleanup_method(api_client, ("async_close", "close"))
        raise

    # Set runtime_data only after successful initialization
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    # runtime_data may not exist if setup failed before it was assigned
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        # Setup failed before coordinator was created, nothing to clean up
        return True

    # Disconnect MQTT client (may not be initialized if setup failed early)
    if coordinator.mqtt_client is not None:
        try:
            await _async_call_cleanup_method(
                coordinator.mqtt_client,
                (
                    "async_disconnect",
                    "disconnect",
                ),
            )
        except Exception:
            _LOGGER.exception("Error disconnecting MQTT client during unload")

    # Close API client (always exists once coordinator is created)
    try:
        await _async_call_cleanup_method(
            coordinator.api_client,
            (
                "async_close",
                "close",
            ),
        )
    except Exception:
        _LOGGER.exception("Error closing API client during unload")

    return True
