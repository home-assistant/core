"""Support for TP-Link LTE modems."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import attr
import tp_connected
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "tplink_lte"
DATA_KEY = "tplink_lte"

CONF_NOTIFY = "notify"

_NOTIFY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_RECIPIENT): vol.All(cv.ensure_list, [cv.string]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_NOTIFY): vol.All(
                            cv.ensure_list, [_NOTIFY_SCHEMA]
                        ),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@attr.s
class ModemData:
    """Class for modem state."""

    host: str = attr.ib()
    modem: tp_connected.Modem = attr.ib()

    connected: bool = attr.ib(init=False, default=True)


@attr.s
class LTEData:
    """Shared state."""

    websession: aiohttp.ClientSession = attr.ib()
    modem_data: dict[str, ModemData] = attr.ib(init=False, factory=dict)

    def get_modem_data(self, config: dict[str, Any]) -> ModemData | None:
        """Get the requested or the only modem_data value."""
        if CONF_HOST in config:
            return self.modem_data.get(config[CONF_HOST])
        if len(self.modem_data) == 1:
            return next(iter(self.modem_data.values()))

        return None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up TP-Link LTE component."""
    if DATA_KEY not in hass.data:
        websession = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        hass.data[DATA_KEY] = LTEData(websession)

    domain_config = config.get(DOMAIN, [])

    tasks = [_setup_lte(hass, conf) for conf in domain_config]
    if tasks:
        await asyncio.gather(*tasks)

    for conf in domain_config:
        for notify_conf in conf.get(CONF_NOTIFY, []):
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, Platform.NOTIFY, DOMAIN, notify_conf, config
                )
            )

    return True


async def _setup_lte(
    hass: HomeAssistant, lte_config: dict[str, Any], delay: int = 0
) -> None:
    """Set up a TP-Link LTE modem."""

    host: str = lte_config[CONF_HOST]
    password: str = lte_config[CONF_PASSWORD]

    lte_data: LTEData = hass.data[DATA_KEY]
    modem = tp_connected.Modem(hostname=host, websession=lte_data.websession)

    modem_data = ModemData(host, modem)

    try:
        await _login(hass, modem_data, password)
    except tp_connected.Error:
        retry_task = hass.loop.create_task(_retry_login(hass, modem_data, password))

        @callback
        def cleanup_retry(event: Event) -> None:
            """Clean up retry task resources."""
            if not retry_task.done():
                retry_task.cancel()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_retry)


async def _login(hass: HomeAssistant, modem_data: ModemData, password: str) -> None:
    """Log in and complete setup."""
    await modem_data.modem.login(password=password)
    modem_data.connected = True
    lte_data: LTEData = hass.data[DATA_KEY]
    lte_data.modem_data[modem_data.host] = modem_data

    async def cleanup(event: Event) -> None:
        """Clean up resources."""
        await modem_data.modem.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)


async def _retry_login(
    hass: HomeAssistant, modem_data: ModemData, password: str
) -> None:
    """Sleep and retry setup."""

    _LOGGER.warning("Could not connect to %s. Will keep trying", modem_data.host)

    modem_data.connected = False
    delay = 15

    while not modem_data.connected:
        await asyncio.sleep(delay)

        try:
            await _login(hass, modem_data, password)
            _LOGGER.warning("Connected to %s", modem_data.host)
        except tp_connected.Error:
            delay = min(2 * delay, 300)
