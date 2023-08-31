"""public IP address Sensor."""
from __future__ import annotations

import asyncio
import base64
from datetime import timedelta
import logging

import aiohttp
from aiohttp.hdrs import AUTHORIZATION, USER_AGENT

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    HA_USER_AGENT,
    MANUFACTURER,
    UPDATE_URL,
)

SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the No-IP.com sensors from config entry."""
    no_ip_domain = config_entry.data[CONF_DOMAIN]
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    async_add_entities([NoIPSensor(no_ip_domain, username, password)])


class NoIPSensor(SensorEntity):
    """NoIPSensor class for No-IP.com."""

    _attr_icon = "mdi:ip"
    _attr_has_entity_name = True

    def __init__(self, no_ip_domain: str, username: str, password: str) -> None:
        """Init NoIPSensor."""
        self._attr_unique_id = no_ip_domain

        self._no_ip_domain = no_ip_domain
        self._username = username
        self._password = password

        self._attr_device_info = DeviceInfo(
            identifiers={(MANUFACTURER, no_ip_domain)},
            manufacturer=MANUFACTURER,
            name=no_ip_domain,
            configuration_url="https://www.home-assistant.io/integrations/no_ip",
        )

    async def async_update(self) -> None:
        """Update the IP address from No-IP.com."""
        auth_str = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode("utf-8")

        session = aiohttp_client.async_create_clientsession(self.hass)
        params = {"hostname": self._no_ip_domain}

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
                        self._no_ip_domain,
                        ip_address,
                    )
                    self._attr_native_value = ip_address
                else:
                    _LOGGER.debug(
                        "Failed to update No-IP.com: %s => %s",
                        self._no_ip_domain,
                        body,
                    )
        except aiohttp.ClientError as client_error:
            _LOGGER.warning("Unable to connect to No-IP.com API: %s", client_error)
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout from No-IP.com API for domain: %s",
                self._no_ip_domain,
            )
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.warning("Error updating data from No-IP.com: %s", e)
