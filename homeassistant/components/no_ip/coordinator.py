"""Coordinator for No-IP.com."""
from __future__ import annotations

import asyncio
import base64
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from aiohttp.hdrs import AUTHORIZATION, USER_AGENT
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    HA_USER_AGENT,
    UPDATE_URL,
)

_LOGGER = logging.getLogger(__name__)


class NoIPDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for No-IP.com."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize No-IP.com data updater."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{entry.entry_id}",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self.config_entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Update the data from No-IP.com."""
        if (
            not self.config_entry
            or not hasattr(self.config_entry, "data")
            or not self.config_entry.data
        ):
            return {}
        no_ip_domain = self.config_entry.data.get(CONF_DOMAIN)
        user = self.config_entry.data.get(CONF_USERNAME)
        password = self.config_entry.data.get(CONF_PASSWORD)

        auth_str = base64.b64encode(f"{user}:{password}".encode()).decode("utf-8")

        session = aiohttp_client.async_create_clientsession(self.hass)
        params = {"hostname": no_ip_domain}

        headers = {
            AUTHORIZATION: f"Basic {auth_str}",
            USER_AGENT: HA_USER_AGENT,
        }

        data: dict[str, Any] = {}

        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                resp = await session.get(UPDATE_URL, params=params, headers=headers)
                body = (await resp.text()).strip()
                if resp.status == 200 and (
                    body.startswith("good") or body.startswith("nochg")
                ):
                    ip_address = body.split(" ")[1]
                    data = {
                        CONF_IP_ADDRESS: ip_address,
                        CONF_DOMAIN: no_ip_domain,
                        CONF_USERNAME: user,
                        CONF_PASSWORD: password,
                    }
                    _LOGGER.debug(
                        "Updating No-IP.com success: %s IP: %s",
                        no_ip_domain,
                        ip_address,
                    )
                else:
                    _LOGGER.debug(
                        "Updating No-IP.com Failed: %s => %s", no_ip_domain, body
                    )
                    data = {
                        CONF_DOMAIN: no_ip_domain,
                    }
        except aiohttp.ClientError:
            _LOGGER.warning("Can't connect to No-IP.com API")
            data = {
                CONF_DOMAIN: no_ip_domain,
            }
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout from No-IP.com API for domain: %s", no_ip_domain)
            data = {
                CONF_DOMAIN: no_ip_domain,
            }
        return data
