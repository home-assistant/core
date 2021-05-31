"""The NFAndroidTV integration."""
from asyncio.exceptions import TimeoutError as TimedOutError
import logging

from async_timeout import timeout
from httpcore import ConnectError

from homeassistant.components.notify import DOMAIN as NOTIFY
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [NOTIFY]


async def async_setup(hass: HomeAssistant, config):
    """Set up the NFAndroidTV component."""
    hass.data.setdefault(DOMAIN, {})
    # Iterate all entries for notify to only get nfandroidtv
    if NOTIFY in config:
        for entry in config[NOTIFY]:
            if entry[CONF_PLATFORM] == DOMAIN:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                    )
                )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NFAndroidTV from a config entry."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]

    try:
        session = async_get_clientsession(hass)
        async with timeout(DEFAULT_TIMEOUT, loop=hass.loop):
            await session.post(f"http://{host}:7676")
    except (ConnectError, TimedOutError) as ex:
        _LOGGER.warning("Failed to connect: %s", ex)
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_HOST: host,
        CONF_NAME: name,
    }

    hass.async_create_task(
        discovery.async_load_platform(
            hass, NOTIFY, DOMAIN, hass.data[DOMAIN][entry.entry_id], hass.data[DOMAIN]
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
