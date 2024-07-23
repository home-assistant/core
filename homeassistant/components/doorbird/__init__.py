"""Support for DoorBird devices."""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

from doorbirdpy import DoorBird
import requests

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_EVENTS, DOMAIN, PLATFORMS
from .device import ConfiguredDoorBird
from .models import DoorBirdData
from .view import DoorBirdRequestView

_LOGGER = logging.getLogger(__name__)

CONF_CUSTOM_URL = "hass_url_override"

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the DoorBird component."""
    hass.data.setdefault(DOMAIN, {})
    # Provide an endpoint for the door stations to call to trigger events
    hass.http.register_view(DoorBirdRequestView)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DoorBird from a config entry."""

    _async_import_options_from_data_if_missing(hass, entry)

    door_station_config = entry.data
    config_entry_id = entry.entry_id

    device_ip = door_station_config[CONF_HOST]
    username = door_station_config[CONF_USERNAME]
    password = door_station_config[CONF_PASSWORD]

    device = DoorBird(device_ip, username, password)
    try:
        status, info = await hass.async_add_executor_job(_init_door_bird_device, device)
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == HTTPStatus.UNAUTHORIZED:
            _LOGGER.error(
                "Authorization rejected by DoorBird for %s@%s", username, device_ip
            )
            return False
        raise ConfigEntryNotReady from err
    except OSError as oserr:
        _LOGGER.error("Failed to setup doorbird at %s: %s", device_ip, oserr)
        raise ConfigEntryNotReady from oserr

    if not status[0]:
        _LOGGER.error(
            "Could not connect to DoorBird as %s@%s: Error %s",
            username,
            device_ip,
            str(status[1]),
        )
        raise ConfigEntryNotReady

    token: str = door_station_config.get(CONF_TOKEN, config_entry_id)
    custom_url: str | None = door_station_config.get(CONF_CUSTOM_URL)
    name: str | None = door_station_config.get(CONF_NAME)
    events = entry.options.get(CONF_EVENTS, [])
    event_entity_ids: dict[str, str] = {}
    door_station = ConfiguredDoorBird(device, name, custom_url, token, event_entity_ids)
    door_bird_data = DoorBirdData(door_station, info, event_entity_ids)
    door_station.update_events(events)
    # Subscribe to doorbell or motion events
    if not await _async_register_events(hass, door_station):
        raise ConfigEntryNotReady

    entry.async_on_unload(entry.add_update_listener(_update_listener))
    hass.data[DOMAIN][config_entry_id] = door_bird_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _init_door_bird_device(device: DoorBird) -> tuple[tuple[bool, int], dict[str, Any]]:
    """Verify we can connect to the device and return the status."""
    return device.ready(), device.info()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data: dict[str, DoorBirdData] = hass.data[DOMAIN]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data.pop(entry.entry_id)
    return unload_ok


async def _async_register_events(
    hass: HomeAssistant, door_station: ConfiguredDoorBird
) -> bool:
    """Register events on device."""
    try:
        await hass.async_add_executor_job(door_station.register_events, hass)
    except requests.exceptions.HTTPError:
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


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    config_entry_id = entry.entry_id
    data: DoorBirdData = hass.data[DOMAIN][config_entry_id]
    door_station = data.door_station
    door_station.update_events(entry.options[CONF_EVENTS])
    # Subscribe to doorbell or motion events
    await _async_register_events(hass, door_station)


@callback
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    options = dict(entry.options)
    modified = False
    for importable_option in (CONF_EVENTS,):
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            modified = True

    if modified:
        hass.config_entries.async_update_entry(entry, options=options)
