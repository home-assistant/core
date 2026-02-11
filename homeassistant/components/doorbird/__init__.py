"""Support for DoorBird devices."""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import ClientResponseError
from doorbirdpy import DoorBird

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_EVENTS, DOMAIN, PLATFORMS
from .device import ConfiguredDoorBird
from .models import DoorBirdConfigEntry, DoorBirdData
from .view import DoorBirdRequestView

CONF_CUSTOM_URL = "hass_url_override"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the DoorBird component."""
    # Provide an endpoint for the door stations to call to trigger events
    hass.http.register_view(DoorBirdRequestView)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DoorBirdConfigEntry) -> bool:
    """Set up DoorBird from a config entry."""
    door_station_config = entry.data
    config_entry_id = entry.entry_id
    device_ip = door_station_config[CONF_HOST]
    username = door_station_config[CONF_USERNAME]
    password = door_station_config[CONF_PASSWORD]
    session = async_get_clientsession(hass)

    device = DoorBird(device_ip, username, password, http_session=session)
    try:
        info = await device.info()
    except ClientResponseError as err:
        if err.status == HTTPStatus.UNAUTHORIZED:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except OSError as oserr:
        raise ConfigEntryNotReady from oserr

    token: str = door_station_config.get(CONF_TOKEN, config_entry_id)
    custom_url: str | None = door_station_config.get(CONF_CUSTOM_URL)
    name: str | None = door_station_config.get(CONF_NAME)
    events = entry.options.get(CONF_EVENTS, [])
    event_entity_ids: dict[str, str] = {}
    door_station = ConfiguredDoorBird(
        hass, device, name, custom_url, token, event_entity_ids
    )
    door_bird_data = DoorBirdData(door_station, info, event_entity_ids)
    door_station.update_events(events)
    # Subscribe to doorbell or motion events
    if not await _async_register_events(hass, door_station, entry):
        raise ConfigEntryNotReady

    entry.async_on_unload(entry.add_update_listener(_update_listener))
    entry.runtime_data = door_bird_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DoorBirdConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_register_events(
    hass: HomeAssistant, door_station: ConfiguredDoorBird, entry: DoorBirdConfigEntry
) -> bool:
    """Register events on device."""
    issue_id = f"doorbird_schedule_error_{entry.entry_id}"
    try:
        await door_station.async_register_events()
    except ClientResponseError as ex:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            severity=ir.IssueSeverity.ERROR,
            translation_key="error_registering_events",
            data={"entry_id": entry.entry_id},
            is_fixable=True,
            translation_placeholders={
                "error": str(ex),
                "name": door_station.name or entry.data[CONF_NAME],
            },
        )
        _LOGGER.debug("Error registering DoorBird events", exc_info=True)
        return False
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)

    return True


async def _update_listener(hass: HomeAssistant, entry: DoorBirdConfigEntry) -> None:
    """Handle options update."""
    door_station = entry.runtime_data.door_station
    door_station.update_events(entry.options[CONF_EVENTS])
    # Subscribe to doorbell or motion events
    await _async_register_events(hass, door_station, entry)
