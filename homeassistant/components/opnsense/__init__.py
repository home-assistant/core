"""Support for OPNsense Routers."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACES, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class OPNsenseClient:
    """Client for the OPNsense API."""

    def __init__(
        self,
        url: str,
        api_key: str,
        api_secret: str,
        session: aiohttp.ClientSession,
        verify_ssl: bool,
    ) -> None:
        """Initialize the OPNsense client."""
        self._url = url.rstrip("/")
        self._auth = aiohttp.BasicAuth(api_key, api_secret)
        self._session = session
        self._verify_ssl = verify_ssl

    async def get_arp(self) -> list[dict[str, Any]]:
        """Get the ARP table from OPNsense."""
        result: list[dict[str, Any]] = await self._get(
            "diagnostics/interface/get_arp"
        )
        return result

    async def get_interfaces(self) -> dict[str, str]:
        """Get available network interfaces from OPNsense."""
        result: dict[str, str] = await self._get(
            "diagnostics/networkinsight/get_interfaces"
        )
        return result

    async def _get(self, endpoint: str) -> Any:
        """Make a GET request to the OPNsense API."""
        url = f"{self._url}/{endpoint}"
        async with self._session.get(
            url,
            auth=self._auth,
            ssl=self._verify_ssl,
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import OPNsense configuration from YAML."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OPNsense from a config entry."""
    data = entry.data
    url = data[CONF_URL]
    api_key = data[CONF_API_KEY]
    api_secret = data[CONF_API_SECRET]
    verify_ssl = data.get(CONF_VERIFY_SSL, False)
    tracker_interfaces_raw = data.get(CONF_TRACKER_INTERFACES, "")

    # Parse tracker interfaces from comma-separated string or list
    if isinstance(tracker_interfaces_raw, list):
        tracker_interfaces = tracker_interfaces_raw
    elif tracker_interfaces_raw:
        tracker_interfaces = [
            i.strip() for i in tracker_interfaces_raw.split(",") if i.strip()
        ]
    else:
        tracker_interfaces = []

    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = OPNsenseClient(url, api_key, api_secret, session, verify_ssl)

    try:
        await client.get_arp()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            "Failed to connect to OPNsense API endpoint"
        ) from err

    if tracker_interfaces:
        try:
            interfaces_resp = await client.get_interfaces()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ConfigEntryNotReady(
                "Failed to retrieve OPNsense network interfaces"
            ) from err
        interfaces = list(interfaces_resp.values())
        for interface in tracker_interfaces:
            if interface not in interfaces:
                _LOGGER.error(
                    "Specified OPNsense tracker interface %s is not found",
                    interface,
                )
                return False

    entry.runtime_data = {
        "client": client,
        "tracker_interfaces": tracker_interfaces,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
