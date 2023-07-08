"""Coordinator for No-IP.com."""
from __future__ import annotations

import base64
from datetime import timedelta
import logging
from typing import Any

from aiohttp.hdrs import AUTHORIZATION, USER_AGENT
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_TIMEOUT, DOMAIN, HA_USER_AGENT, UPDATE_URL

_LOGGER = logging.getLogger(__name__)


class NoIPDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for No-IP.com."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize No-IP.com data updater."""
        intervale = entry.options.get(CONF_TIMEOUT, 5)
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{entry.entry_id}",
            update_interval=timedelta(minutes=intervale),
        )
        self.config_entry = entry

        self.no_ip_domain = self.config_entry.data[CONF_DOMAIN]
        self.params = {"hostname": self.no_ip_domain}

        self.timeout = self.config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        user = self.config_entry.data[CONF_USERNAME]
        password = self.config_entry.data[CONF_PASSWORD]
        auth_str = base64.b64encode(f"{user}:{password}".encode())

        self.headers = {
            AUTHORIZATION: f"Basic {auth_str.decode('utf-8')}",
            USER_AGENT: HA_USER_AGENT,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Update the data from No-IP.com."""

        data: dict[str, Any] = {}

        session = aiohttp_client.async_create_clientsession(self.hass)

        async with async_timeout.timeout(self.timeout):
            resp = await session.get(
                UPDATE_URL, params=self.params, headers=self.headers
            )
            body = await resp.text()

            if body.startswith("good") or body.startswith("nochg"):
                ipAddress = str(body.split(" ")[1]).strip()
                _LOGGER.debug(
                    "Updating No-IP.com success: %s IP: %s",
                    self.no_ip_domain,
                    ipAddress,
                )

                data = {
                    CONF_IP_ADDRESS: ipAddress,
                    CONF_DOMAIN: self.no_ip_domain,
                }
            else:
                _LOGGER.debug(
                    "Updating No-IP.com Failed: %s => %s",
                    self.no_ip_domain,
                    body.strip(),
                )
        return data
