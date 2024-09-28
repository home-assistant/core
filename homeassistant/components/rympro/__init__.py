"""The Read Your Meter Pro integration."""

from __future__ import annotations

import logging

from pyrympro import CannotConnectError, RymPro, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import RymProDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Read Your Meter Pro from a config entry."""
    data = entry.data
    rympro = RymPro(async_get_clientsession(hass))
    rympro.set_token(data[CONF_TOKEN])
    try:
        await rympro.account_info()
    except CannotConnectError as error:
        raise ConfigEntryNotReady from error
    except UnauthorizedError:
        try:
            token = await rympro.login(data[CONF_EMAIL], data[CONF_PASSWORD], "ha")
        except UnauthorizedError as error:
            raise ConfigEntryAuthFailed from error
        hass.config_entries.async_update_entry(
            entry,
            data={**data, CONF_TOKEN: token},
        )

    coordinator = RymProDataUpdateCoordinator(hass, rympro)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
