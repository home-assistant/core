"""The caldav component."""
from __future__ import annotations

import logging

import caldav

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CALDAV_EXCEPTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Caldav component."""
    try:
        calendars = await async_caldav_connect(hass, entry.data)
    except CALDAV_EXCEPTIONS as error:
        raise ConfigEntryNotReady from error

    device_registry = dr.async_get(hass)
    for stable_parent_url in {calendar.parent.canonical_url for calendar in calendars}:
        device_registry.async_get_or_create(
            name=entry.data[CONF_USERNAME],
            config_entry_id=entry.entry_id,
            model="CalDAV Service",
            configuration_url=stable_parent_url,
            entry_type=dr.DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, stable_parent_url)},
        )

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = calendars
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload device tracker if change option."""
    await hass.config_entries.async_reload(entry.entry_id)


def _caldav_connect(client: caldav.DAVClient) -> list[caldav.Calendar]:
    """Return the calendars for the client."""
    return client.principal().calendars()


async def async_caldav_connect(hass, data_entry):
    """Connect to caldav server."""
    client = caldav.DAVClient(
        url=data_entry[CONF_URL],
        username=data_entry[CONF_USERNAME],
        password=data_entry[CONF_PASSWORD],
        ssl_verify_cert=data_entry[CONF_VERIFY_SSL],
    )
    return await hass.async_add_executor_job(_caldav_connect, client)
