"""Config flow for Yamaha."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.storage import Store

from .const import (
    CONF_SERIAL,
    DISCOVERY_STORE,
    DISCOVERY_STORE_KEY,
    DISCOVERY_STORE_VERSION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class YamahaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a MusicCast config flow."""

    VERSION = 1

    serial_number: str | None = None
    host: str
    ctrl_url: str
    upnp_description: str | None = None

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> data_entry_flow.ConfigFlowResult:
        """Handle ssdp discoveries."""
        _LOGGER.debug("SSDP Discover %s", discovery_info)

        self.serial_number = discovery_info.upnp[ssdp.ATTR_UPNP_SERIAL]
        self.upnp_description = discovery_info.ssdp_location
        try:
            self.host = str(urlparse(discovery_info.ssdp_location).hostname)
        except ValueError:
            _LOGGER.error("SSDP urlparse location %s", discovery_info.ssdp_location)
            return self.async_abort(reason="urlparse fail")

        self.ctrl_url = f"http://{self.host}:80/YamahaRemoteControl/ctrl"

        if (DOMAIN in self.hass.data) and (DISCOVERY_STORE in self.hass.data[DOMAIN]):
            _LOGGER.debug("Reusing Store")
            store: Store[dict[str, Any]] = self.hass.data[DOMAIN][DISCOVERY_STORE]
        else:
            _LOGGER.debug("Creating Store")
            store = Store[dict[str, Any]](
                self.hass, DISCOVERY_STORE_VERSION, DISCOVERY_STORE_KEY
            )

        data = await store.async_load()
        if not data:
            data = {}
        _LOGGER.debug("Discovery Store %s", data)
        if (self.ctrl_url not in data) or (
            self.ctrl_url in data
            and data[self.ctrl_url][CONF_SERIAL] != self.serial_number
        ):
            _LOGGER.debug("Recording serial %s %s", self.ctrl_url, self.serial_number)
            data[self.ctrl_url] = {
                "serial_number": self.serial_number,
            }
            await store.async_save(data)

        await self.async_set_unique_id(self.serial_number)
        return self.async_abort(reason="serial recorded")
