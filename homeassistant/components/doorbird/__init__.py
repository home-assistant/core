"""Support for DoorBird devices."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp import ClientResponseError
from doorbirdpy import DoorBird

from homeassistant.components import persistent_notification
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_EVENTS, DOMAIN, PLATFORMS
from .device import ConfiguredDoorBird
from .models import DoorBirdConfigEntry, DoorBirdData
from .view import DoorBirdRequestView

CONF_CUSTOM_URL = "hass_url_override"

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


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
    if not await _async_register_events(hass, door_station):
        raise ConfigEntryNotReady

    entry.async_on_unload(entry.add_update_listener(_update_listener))
    entry.runtime_data = door_bird_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DoorBirdConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_register_events(
    hass: HomeAssistant, door_station: ConfiguredDoorBird
) -> bool:
    """Register events on device."""
    try:
        await door_station.async_register_events()
    except ClientResponseError:
        persistent_notification.async_create(
            hass,
            (
                "Doorbird configuration failed.  Please verify that API "
                "Operator permission is enabled for the Doorbird user. "
                "A restart will be required once permissions have been "
                "verified."
            ),
            title="Doorbird Configuration Failure",
            notification_id="doorbird_schedule_error",
        )
        return False

    return True


async def _update_listener(hass: HomeAssistant, entry: DoorBirdConfigEntry) -> None:
    """Handle options update."""
    door_station = entry.runtime_data.door_station
    door_station.update_events(entry.options[CONF_EVENTS])
    # Subscribe to doorbell or motion events
    await _async_register_events(hass, door_station)
