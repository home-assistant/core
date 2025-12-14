"""Support for Google - Calendar Event Devices."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp
from gcal_sync.api import GoogleCalendarService
from gcal_sync.exceptions import ApiException, AuthException
import voluptuous as vol
import yaml

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_OFFSET,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import generate_entity_id

from .api import ApiAuthImpl, get_feature_access
from .const import DOMAIN
from .store import GoogleConfigEntry, GoogleRuntimeData, LocalCalendarStore

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_TRACK_NEW = "track_new_calendar"

CONF_CAL_ID = "cal_id"
CONF_TRACK = "track"
CONF_SEARCH = "search"
CONF_IGNORE_AVAILABILITY = "ignore_availability"
CONF_MAX_RESULTS = "max_results"

DEFAULT_CONF_OFFSET = "!!"

YAML_DEVICES = f"{DOMAIN}_calendars.yaml"

PLATFORMS = [Platform.CALENDAR]


CONFIG_SCHEMA = vol.Schema(cv.removed(DOMAIN), extra=vol.ALLOW_EXTRA)


_SINGLE_CALSEARCH_CONFIG = vol.All(
    cv.deprecated(CONF_MAX_RESULTS),
    vol.Schema(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_DEVICE_ID): cv.string,
            vol.Optional(CONF_IGNORE_AVAILABILITY, default=True): cv.boolean,
            vol.Optional(CONF_OFFSET): cv.string,
            vol.Optional(CONF_SEARCH): cv.string,
            vol.Optional(CONF_TRACK): cv.boolean,
            vol.Optional(CONF_MAX_RESULTS): cv.positive_int,  # Now unused
        }
    ),
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CAL_ID): cv.string,
        vol.Required(CONF_ENTITIES, None): vol.All(
            cv.ensure_list, [_SINGLE_CALSEARCH_CONFIG]
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: GoogleConfigEntry) -> bool:
    """Set up Google from a config entry."""
    # Validate google_calendars.yaml (if present) as soon as possible to return
    # helpful error messages.
    try:
        await hass.async_add_executor_job(load_config, hass.config.path(YAML_DEVICES))
    except vol.Invalid as err:
        _LOGGER.error("Configuration error in %s: %s", YAML_DEVICES, str(err))
        return False

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    # Force a token refresh to fix a bug where tokens were persisted with
    # expires_in (relative time delta) and expires_at (absolute time) swapped.
    # A google session token typically only lasts a few days between refresh.
    now = datetime.now()
    if session.token["expires_at"] >= (now + timedelta(days=365)).timestamp():
        session.token["expires_in"] = 0
        session.token["expires_at"] = now.timestamp()
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    if not async_entry_has_scopes(entry):
        raise ConfigEntryAuthFailed(
            "Required scopes are not available, reauth required"
        )
    calendar_service = GoogleCalendarService(
        ApiAuthImpl(async_get_clientsession(hass), session)
    )
    entry.runtime_data = GoogleRuntimeData(
        service=calendar_service,
        store=LocalCalendarStore(hass, entry.entry_id),
    )

    if entry.unique_id is None:
        try:
            primary_calendar = await calendar_service.async_get_calendar("primary")
        except AuthException as err:
            raise ConfigEntryAuthFailed from err
        except ApiException as err:
            raise ConfigEntryNotReady from err

        hass.config_entries.async_update_entry(entry, unique_id=primary_calendar.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def async_entry_has_scopes(entry: GoogleConfigEntry) -> bool:
    """Verify that the config entry desired scope is present in the oauth token."""
    access = get_feature_access(entry)
    token_scopes = entry.data.get("token", {}).get("scope", [])
    return access.scope in token_scopes


async def async_unload_entry(hass: HomeAssistant, entry: GoogleConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: GoogleConfigEntry) -> None:
    """Handle removal of a local storage."""
    store = LocalCalendarStore(hass, entry.entry_id)
    await store.async_remove()


def get_calendar_info(
    hass: HomeAssistant, calendar: Mapping[str, Any]
) -> dict[str, Any]:
    """Convert data from Google into DEVICE_SCHEMA."""
    calendar_info: dict[str, Any] = DEVICE_SCHEMA(
        {
            CONF_CAL_ID: calendar["id"],
            CONF_ENTITIES: [
                {
                    CONF_NAME: calendar["summary"],
                    CONF_DEVICE_ID: generate_entity_id(
                        "{}", calendar["summary"], hass=hass
                    ),
                }
            ],
        }
    )
    return calendar_info


def load_config(path: str) -> dict[str, Any]:
    """Load the google_calendar_devices.yaml."""
    calendars = {}
    try:
        with open(path, encoding="utf8") as file:
            data = yaml.safe_load(file) or []
            for calendar in data:
                calendars[calendar[CONF_CAL_ID]] = DEVICE_SCHEMA(calendar)
    except FileNotFoundError as err:
        _LOGGER.debug("Error reading calendar configuration: %s", err)
        # When YAML file could not be loaded/did not contain a dict
        return {}

    return calendars


def update_config(path: str, calendar: dict[str, Any]) -> None:
    """Write the google_calendar_devices.yaml."""
    try:
        with open(path, "a", encoding="utf8") as out:
            out.write("\n")
            yaml.dump([calendar], out, default_flow_style=False)
    except FileNotFoundError as err:
        _LOGGER.debug("Error persisting calendar configuration: %s", err)
