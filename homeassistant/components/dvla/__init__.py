"""The DVLA integration."""

import logging
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONTENT_TYPE_JSON, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import API_KEY, ATTR_REG_NUMBER, DOMAIN, HOST, SCHEMA_URL, SERVICE_LOOKUP

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

LOOKUP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_REG_NUMBER): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_get_schema(hass: HomeAssistant) -> dict[str, Any]:
    """Fetch the DVLA API schema."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(SCHEMA_URL) as response:
            if response.status == 200:
                return await response.json()
    except (TimeoutError, ClientError, ValueError) as err:
        _LOGGER.debug("Failed to fetch DVLA schema: %s", err)
    return {}


async def _async_single_lookup(hass: HomeAssistant, reg_number: str) -> Any:
    """Perform a one-off DVLA lookup."""

    session = async_get_clientsession(hass)

    try:
        resp = await session.post(
            HOST,
            headers={
                "Content-Type": CONTENT_TYPE_JSON,
                "x-api-key": API_KEY,
            },
            json={"registrationNumber": str(reg_number).upper()},
        )
        body = await resp.json()
    except ValueError as err:
        _LOGGER.exception("Failed to parse DVLA response")
        raise HomeAssistantError("Invalid response from DVLA API") from err

    if "errors" in body:
        error = body["errors"][0]
        raise HomeAssistantError(
            f"{error.get('title')}({error.get('code')}): {error.get('detail')}"
        )

    if "message" in body:
        raise HomeAssistantError(body["message"])

    if resp.status >= 400:
        raise HomeAssistantError(
            f"DVLA lookup failed with status {resp.status}: {body}"
        )

    return body


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the DVLA integration."""

    async def handle_lookup(call: ServiceCall) -> dict[str, Any]:
        """Handle dvla.lookup service."""
        reg_number = call.data[ATTR_REG_NUMBER]
        return await _async_single_lookup(hass, reg_number)

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOOKUP,
        handle_lookup,
        schema=LOOKUP_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    schema = await async_get_schema(hass)

    hass_data = dict(entry.data)
    hass_data["schema"] = schema

    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)

    # Use async_on_unload to register the listener without storing it in entry data
    entry.async_on_unload(unsub_options_update_listener)

    entry.runtime_data = hass_data

    # Forward the setup to each platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def options_update_listener(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Handle options update."""
    entry = hass.config_entries.async_get_entry(config_entry.entry_id)

    if entry is None:
        return

    # Proceed only if the entry is in a valid state.
    if entry.state not in (
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.SETUP_RETRY,
    ):
        await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
