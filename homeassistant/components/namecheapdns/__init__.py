"""Support for namecheap DNS services."""

from datetime import timedelta
import logging

from aiohttp import ClientError, ClientSession
import defusedxml.ElementTree as ET
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, UPDATE_URL

_LOGGER = logging.getLogger(__name__)


INTERVAL = timedelta(minutes=5)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_HOST, default="@"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

type NamecheapConfigEntry = ConfigEntry[None]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the namecheap DNS component."""

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: NamecheapConfigEntry) -> bool:
    """Set up Namecheap DynamicDNS from a config entry."""
    host = entry.data[CONF_HOST]
    domain = entry.data[CONF_DOMAIN]
    password = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass)

    try:
        if not await update_namecheapdns(session, host, domain, password):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    CONF_DOMAIN: f"{entry.data[CONF_HOST]}.{entry.data[CONF_DOMAIN]}"
                },
            )
    except ClientError as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={
                CONF_DOMAIN: f"{entry.data[CONF_HOST]}.{entry.data[CONF_DOMAIN]}"
            },
        ) from e

    async def update_domain_interval(now):
        """Update the namecheap DNS entry."""
        await update_namecheapdns(session, host, domain, password)

    entry.async_on_unload(
        async_track_time_interval(hass, update_domain_interval, INTERVAL)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NamecheapConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def update_namecheapdns(
    session: ClientSession, host: str, domain: str, password: str
):
    """Update namecheap DNS entry."""
    params = {"host": host, "domain": domain, "password": password}

    resp = await session.get(UPDATE_URL, params=params)
    xml_string = await resp.text()
    root = ET.fromstring(xml_string)
    err_count = root.find("ErrCount").text

    if int(err_count) != 0:
        _LOGGER.warning("Updating namecheap domain failed: %s", domain)
        return False

    return True
