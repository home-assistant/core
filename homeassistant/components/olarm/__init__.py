"""The olarm integration."""

from __future__ import annotations

import logging

from olarmflowclient import OlarmFlowClientApiError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
)
from .coordinator import OlarmFlowClientCoordinator

type OlarmConfigEntry = ConfigEntry[OlarmFlowClientCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_PLATFORMS = [
    Platform.BINARY_SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OlarmConfigEntry) -> bool:
    """Set up olarm from a config entry."""
    _LOGGER.debug(
        "Setting up Olarm integration for device: %s", entry.data.get("device_id")
    )

    # use oauth2 to get access token
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    _LOGGER.debug(
        "OAuth2 session created, access_token expires at -> %s",
        session.token["expires_at"],
    )

    try:
        # setup Olarm Connect coordinator
        coordinator = await hass.async_add_executor_job(
            OlarmFlowClientCoordinator,
            hass,
            entry.data["user_id"],
            entry.data["device_id"],
            session.token["access_token"],
            session,
        )

        # fetch device
        _LOGGER.debug("Fetching device information from Olarm API")
        await coordinator.get_device()

        # connect to MQTT
        _LOGGER.debug("Connecting to Olarm MQTT service")
        await coordinator.init_mqtt()

        # store coordinator in entry.runtime_data
        entry.runtime_data = coordinator

        _LOGGER.debug("Setting up platforms for Olarm integration")
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    except ConfigEntryNotReady:
        # Temporary failures (network issues, device offline, etc.) - let Home Assistant retry
        _LOGGER.debug("Olarm setup not ready, will retry later")
        raise
    except ConfigEntryAuthFailed:
        # Authentication failures - Home Assistant will trigger reauthentication
        _LOGGER.error("Olarm authentication failed")
        raise
    except ConfigEntryError:
        # Permanent failures - setup will not be retried
        _LOGGER.error("Permanent error setting up Olarm integration")
        raise
    except OlarmFlowClientApiError as ex:
        # API errors that indicate authentication or permanent issues
        if "401" in str(ex) or "403" in str(ex) or "unauthorized" in str(ex).lower():
            _LOGGER.error("Olarm API authentication failed: %s", ex)
            raise ConfigEntryAuthFailed("Invalid Olarm credentials") from ex
        _LOGGER.warning("Olarm API error during setup: %s", ex)
        raise ConfigEntryNotReady("Olarm API temporarily unavailable") from ex
    except (OSError, ConnectionError, TimeoutError) as ex:
        # Network-related errors that are likely temporary
        _LOGGER.warning("Network error during Olarm setup: %s", ex)
        raise ConfigEntryNotReady("Network connection to Olarm failed") from ex
    except Exception as ex:
        # Unexpected errors - log and treat as temporary to avoid permanent failure
        _LOGGER.exception("Unexpected error setting up Olarm integration")
        # Clean up any partial setup
        if hasattr(entry, "runtime_data") and entry.runtime_data:
            coordinator = entry.runtime_data
            if coordinator:
                try:
                    await coordinator.async_stop()
                except (OSError, ConnectionError, RuntimeError) as cleanup_error:
                    _LOGGER.error("Error during cleanup: %s", cleanup_error)
        raise ConfigEntryNotReady("Unexpected error during Olarm setup") from ex

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OlarmConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = entry.runtime_data

    # stop coordinator
    await coordinator.async_stop()

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
