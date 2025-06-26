"""The olarm integration."""

from __future__ import annotations

import logging

from olarmflowclient import OlarmFlowClientApiError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_LINK_ID,
    ATTR_OUTPUT_ACTION,
    ATTR_OUTPUT_INDEX,
    ATTR_PGM_ACTION,
    ATTR_PGM_INDEX,
    ATTR_RELAY_ACTION,
    ATTR_RELAY_INDEX,
    ATTR_UKEY_INDEX,
    ATTR_ZONE_INDEX,
    DOMAIN,
    SERVICE_LINK_OUTPUT_COMMAND,
    SERVICE_LINK_RELAY_COMMAND,
    SERVICE_MAX_OUTPUT_COMMAND,
    SERVICE_PGM_COMMAND,
    SERVICE_UTILITY_KEY,
    SERVICE_ZONE_BYPASS,
    SERVICE_ZONE_UNBYPASS,
)
from .coordinator import OlarmFlowClientCoordinator

type OlarmConfigEntry = ConfigEntry[OlarmFlowClientCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_ZONE_BYPASS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_INDEX): cv.positive_int,
    }
)

SERVICE_ZONE_UNBYPASS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_INDEX): cv.positive_int,
    }
)

SERVICE_PGM_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PGM_INDEX): cv.positive_int,
        vol.Required(ATTR_PGM_ACTION): vol.In(["open", "close", "pulse"]),
    }
)

SERVICE_UTILITY_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_UKEY_INDEX): cv.positive_int,
    }
)

SERVICE_LINK_OUTPUT_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_LINK_ID): cv.string,
        vol.Required(ATTR_OUTPUT_INDEX): cv.positive_int,
        vol.Required(ATTR_OUTPUT_ACTION): vol.In(["open", "close", "pulse"]),
    }
)

SERVICE_LINK_RELAY_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_LINK_ID): cv.string,
        vol.Required(ATTR_RELAY_INDEX): cv.positive_int,
        vol.Required(ATTR_RELAY_ACTION): vol.In(["latch", "unlatch", "pulse"]),
    }
)

SERVICE_MAX_OUTPUT_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_OUTPUT_INDEX): cv.positive_int,
        vol.Required(ATTR_OUTPUT_ACTION): vol.In(["open", "close", "pulse"]),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Olarm integration."""

    async def async_zone_bypass(call: ServiceCall) -> None:
        """Bypass a zone."""
        if not (
            entry := hass.config_entries.async_get_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        ):
            raise ServiceValidationError("Config entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Config entry not loaded")
        coordinator = entry.runtime_data
        await coordinator.send_device_zone_cmd(
            entry.data["device_id"], "bypass", call.data[ATTR_ZONE_INDEX]
        )

    async def async_zone_unbypass(call: ServiceCall) -> None:
        """Unbypass a zone."""
        if not (
            entry := hass.config_entries.async_get_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        ):
            raise ServiceValidationError("Config entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Config entry not loaded")
        coordinator = entry.runtime_data
        await coordinator.send_device_zone_cmd(
            entry.data["device_id"], "unbypass", call.data[ATTR_ZONE_INDEX]
        )

    async def async_pgm_command(call: ServiceCall) -> None:
        """Send a PGM command."""
        if not (
            entry := hass.config_entries.async_get_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        ):
            raise ServiceValidationError("Config entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Config entry not loaded")
        coordinator = entry.runtime_data
        await coordinator.send_device_pgm_cmd(
            entry.data["device_id"],
            call.data[ATTR_PGM_ACTION],
            call.data[ATTR_PGM_INDEX],
        )

    async def async_utility_key(call: ServiceCall) -> None:
        """Send a utility key command."""
        if not (
            entry := hass.config_entries.async_get_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        ):
            raise ServiceValidationError("Config entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Config entry not loaded")
        coordinator = entry.runtime_data
        await coordinator.send_device_ukey_cmd(
            entry.data["device_id"], call.data[ATTR_UKEY_INDEX]
        )

    async def async_link_output_command(call: ServiceCall) -> None:
        """Send a LINK output command."""
        if not (
            entry := hass.config_entries.async_get_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        ):
            raise ServiceValidationError("Config entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Config entry not loaded")
        coordinator = entry.runtime_data
        await coordinator.send_device_link_output_cmd(
            entry.data["device_id"],
            call.data[ATTR_LINK_ID],
            call.data[ATTR_OUTPUT_ACTION],
            call.data[ATTR_OUTPUT_INDEX],
        )

    async def async_link_relay_command(call: ServiceCall) -> None:
        """Send a LINK relay command."""
        if not (
            entry := hass.config_entries.async_get_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        ):
            raise ServiceValidationError("Config entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Config entry not loaded")
        coordinator = entry.runtime_data
        await coordinator.send_device_link_relay_cmd(
            entry.data["device_id"],
            call.data[ATTR_LINK_ID],
            call.data[ATTR_RELAY_ACTION],
            call.data[ATTR_RELAY_INDEX],
        )

    async def async_max_output_command(call: ServiceCall) -> None:
        """Send a MAX output command."""
        if not (
            entry := hass.config_entries.async_get_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        ):
            raise ServiceValidationError("Config entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Config entry not loaded")
        coordinator = entry.runtime_data
        await coordinator.send_device_max_output_cmd(
            entry.data["device_id"],
            call.data[ATTR_OUTPUT_ACTION],
            call.data[ATTR_OUTPUT_INDEX],
        )

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_ZONE_BYPASS,
        async_zone_bypass,
        schema=SERVICE_ZONE_BYPASS_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ZONE_UNBYPASS,
        async_zone_unbypass,
        schema=SERVICE_ZONE_UNBYPASS_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PGM_COMMAND,
        async_pgm_command,
        schema=SERVICE_PGM_COMMAND_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UTILITY_KEY,
        async_utility_key,
        schema=SERVICE_UTILITY_KEY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LINK_OUTPUT_COMMAND,
        async_link_output_command,
        schema=SERVICE_LINK_OUTPUT_COMMAND_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LINK_RELAY_COMMAND,
        async_link_relay_command,
        schema=SERVICE_LINK_RELAY_COMMAND_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_MAX_OUTPUT_COMMAND,
        async_max_output_command,
        schema=SERVICE_MAX_OUTPUT_COMMAND_SCHEMA,
    )

    return True


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
