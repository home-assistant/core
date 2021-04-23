"""The brunt component."""
import asyncio
import logging

from aiohttp.web_exceptions import HTTPError
from brunt import BruntClientAsync

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS = ["cover"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Component setup, run import config flow for each entry in config."""
    if DOMAIN not in config:
        return True
    hass.data.setdefault(DOMAIN, {})
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Brunt using config flow."""
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    bapi = BruntClientAsync(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )
    try:
        await bapi.async_login()
    except HTTPError as exc:
        raise ConfigEntryAuthFailed(
            f"Brunt could not connect with username: {entry.data[CONF_USERNAME]}."
        ) from exc
    # try:
    #     await bapi.async_get_things(force=True)
    # except HTTPError as exc:
    #     raise ConfigEntryNotReady("Brunt could not load things.") from exc
    hass.data[DOMAIN][entry.entry_id] = bapi
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "cover")
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
