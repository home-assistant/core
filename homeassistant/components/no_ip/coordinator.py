"""Coordinator for No-IP.com."""
from __future__ import annotations

import asyncio
import base64
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from aiohttp.hdrs import AUTHORIZATION, USER_AGENT

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
        self._entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Update the data from No-IP.com."""

        data: dict[str, Any] = {
            CONF_DOMAIN: self._entry.data.get(CONF_DOMAIN),
            CONF_IP_ADDRESS: None,
            CONF_USERNAME: self._entry.data.get(CONF_USERNAME),
            CONF_PASSWORD: self._entry.data.get(CONF_PASSWORD),
        }

        no_ip_domain = self._entry.data.get(CONF_DOMAIN)
        user = self._entry.data.get(CONF_USERNAME)
        password = self._entry.data.get(CONF_PASSWORD)

        auth_str = base64.b64encode(f"{user}:{password}".encode()).decode("utf-8")

        session = aiohttp_client.async_create_clientsession(self.hass)
        params = {"hostname": no_ip_domain}

        headers = {
            AUTHORIZATION: f"Basic {auth_str}",
            USER_AGENT: HA_USER_AGENT,
        }

        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT), session.get(
                UPDATE_URL, params=params, headers=headers
            ) as resp:
                body = await resp.text()
                body = body.strip()
                if body.startswith("good") or body.startswith("nochg"):
                    ip_address = body.split(" ")[1]
                    _LOGGER.debug(
                        "Successfully updated No-IP.com: %s IP: %s",
                        no_ip_domain,
                        ip_address,
                    )
                    data.update(
                        {
                            CONF_IP_ADDRESS: ip_address,
                            CONF_DOMAIN: no_ip_domain,
                            CONF_USERNAME: user,
                            CONF_PASSWORD: password,
                        }
                    )
                else:
                    _LOGGER.debug(
                        "Failed to update No-IP.com: %s => %s",
                        no_ip_domain,
                        body,
                    )
        except aiohttp.ClientError as client_error:
            _LOGGER.warning("Unable to connect to No-IP.com API: %s", client_error)
            raise
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout from No-IP.com API for domain: %s",
                no_ip_domain,
            )
            raise
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.warning("Error updating data from No-IP.com: %s", e)
            raise

        return data
