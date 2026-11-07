"""LANBON LOIP integration setup. I/O goes only through aiolanbon."""

import logging
import re

from aiolanbon import LanbonClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_GATEWAY_ID, CONF_SCHEME, DOMAIN, MANUFACTURER
from .coordinator import LanbonCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]

type LanbonConfigEntry = ConfigEntry[LanbonCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LanbonConfigEntry) -> bool:
    """Set up LANBON from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    token = entry.data[CONF_TOKEN]
    scheme = entry.data.get(CONF_SCHEME, "http")
    session = async_get_clientsession(hass)
    client = LanbonClient(host, port, token, session, scheme=scheme)
    coordinator = LanbonCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    info = coordinator.info
    assert info is not None
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, info.gateway_id)},
        connections=(
            {(dr.CONNECTION_NETWORK_MAC, info.gateway_id)}
            if re.fullmatch(r"[0-9a-f]{12}", info.gateway_id)
            else set()
        ),
        manufacturer=info.manufacturer or MANUFACTURER,
        model=info.model,
        name=info.model or MANUFACTURER,
        sw_version=info.firmware_version,
        hw_version=info.hardware_version,
    )
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_on_unload)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug(
        "LANBON LOIP setup host=%s gateway=%s",
        host,
        entry.data.get(CONF_GATEWAY_ID, ""),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LanbonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
