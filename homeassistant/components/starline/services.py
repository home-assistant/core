"""Services for the StarLine integration."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service

from .const import (
    CONF_SCAN_OBD_INTERVAL,
    DOMAIN,
    SERVICE_SET_SCAN_INTERVAL,
    SERVICE_SET_SCAN_OBD_INTERVAL,
    SERVICE_UPDATE_STATE,
)

if TYPE_CHECKING:
    from . import StarlineConfigEntry

SET_SCAN_INTERVAL_SCHEMA = vol.Schema(
    {vol.Required(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=10))}
)

SET_SCAN_OBD_INTERVAL_SCHEMA = vol.Schema(
    {vol.Required(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=180))}
)


def _get_config_entry(hass: HomeAssistant) -> StarlineConfigEntry:
    """Return the loaded StarLine config entry."""
    return service.async_get_config_entry(hass, DOMAIN, None)


async def _async_update(call: ServiceCall) -> None:
    """Update all data."""
    account = _get_config_entry(call.hass).runtime_data
    await account.update()
    await account.update_obd()


async def _async_set_scan_interval(call: ServiceCall) -> None:
    """Set scan interval."""
    entry = _get_config_entry(call.hass)
    options = dict(entry.options)
    options[CONF_SCAN_INTERVAL] = call.data[CONF_SCAN_INTERVAL]
    call.hass.config_entries.async_update_entry(entry=entry, options=options)


async def _async_set_scan_obd_interval(call: ServiceCall) -> None:
    """Set OBD info scan interval."""
    entry = _get_config_entry(call.hass)
    options = dict(entry.options)
    options[CONF_SCAN_OBD_INTERVAL] = call.data[CONF_SCAN_INTERVAL]
    call.hass.config_entries.async_update_entry(entry=entry, options=options)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register StarLine services."""

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_STATE, _async_update)
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCAN_INTERVAL,
        _async_set_scan_interval,
        schema=SET_SCAN_INTERVAL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCAN_OBD_INTERVAL,
        _async_set_scan_obd_interval,
        schema=SET_SCAN_OBD_INTERVAL_SCHEMA,
    )
