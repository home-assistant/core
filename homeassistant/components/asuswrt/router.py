"""Represent the AsusWrt router."""
from typing import Dict

from aioasuswrt.asuswrt import AsusWrt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    PROTOCOL_TELNET,
)

CONF_REQ_RELOAD = [CONF_DNSMASQ, CONF_INTERFACE, CONF_REQUIRE_IP]


class AsusWrtRouter:
    """Representation of a AsusWrt router."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry) -> None:
        """Initialize a AsusWrt router."""
        self.hass = hass
        self._entry = entry
        self._api: AsusWrt = None
        self._protocol = entry.data[CONF_PROTOCOL]

        self._options = {
            CONF_DNSMASQ: DEFAULT_DNSMASQ,
            CONF_INTERFACE: DEFAULT_INTERFACE,
            CONF_REQUIRE_IP: True,
        }
        self._options.update(entry.options)

    async def setup(self) -> None:
        """Set up a AsusWrt router."""
        self._api = get_api(self._entry.data, self._options)

        try:
            await self._api.connection.async_connect()
        except OSError as exp:
            raise ConfigEntryNotReady from exp

        if not self._api.is_connected:
            raise ConfigEntryNotReady

    async def close(self) -> None:
        """Close the connection."""
        if self._api is not None:
            if self._protocol == PROTOCOL_TELNET:
                await self._api.connection.disconnect()
        self._api = None

    def update_options(self, new_options: Dict) -> bool:
        """Update router options."""
        req_reload = False
        for name, new_opt in new_options.items():
            if name in (CONF_REQ_RELOAD):
                old_opt = self._options.get(name)
                if not old_opt or old_opt != new_opt:
                    req_reload = True
                    break

        self._options.update(new_options)
        return req_reload

    @property
    def api(self) -> AsusWrt:
        """Return router API."""
        return self._api


def get_api(conf: Dict, options: Dict = {}) -> AsusWrt:
    """Get the AsusWrt API."""

    return AsusWrt(
        conf[CONF_HOST],
        conf[CONF_PORT],
        conf[CONF_PROTOCOL] == PROTOCOL_TELNET,
        conf[CONF_USERNAME],
        conf.get(CONF_PASSWORD, ""),
        conf.get(CONF_SSH_KEY, ""),
        conf[CONF_MODE],
        options.get(CONF_REQUIRE_IP, True),
        interface=options.get(CONF_INTERFACE, DEFAULT_INTERFACE),
        dnsmasq=options.get(CONF_DNSMASQ, DEFAULT_DNSMASQ),
    )
