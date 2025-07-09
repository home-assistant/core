"""Config flow for Droplet integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_HOST,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_PORT,
    CONF_SERIAL,
    CONF_SW,
    DEVICE_NAME,
    DOMAIN,
)
from .dropletmqtt import DropletDiscovery

_LOGGER = logging.getLogger(__name__)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Droplet config flow."""

    VERSION = 1

    _droplet_discovery: DropletDiscovery | None = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._droplet_discovery = DropletDiscovery(
            discovery_info.host,
            discovery_info.port,
            discovery_info.name,
            discovery_info.properties,
        )
        if self._droplet_discovery is None or not self._droplet_discovery.is_valid():
            return self.async_abort(reason="invalid_discovery_info")

        await self.async_set_unique_id(f"{self._droplet_discovery.device_id}")
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if self._droplet_discovery is None:
            return self.async_abort(reason="device_not_found")
        if self._droplet_discovery.device_id is None:
            return self.async_abort(reason="invalid_discovery_info")
        if user_input is not None:
            device_data = {
                CONF_HOST: self._droplet_discovery.host,
                CONF_PORT: self._droplet_discovery.port,
                CONF_DEVICE_ID: self._droplet_discovery.device_id,
                CONF_DEVICE_NAME: DEVICE_NAME,
                CONF_MODEL: self._droplet_discovery.properties.get(CONF_MODEL),
                CONF_MANUFACTURER: self._droplet_discovery.properties.get(
                    CONF_MANUFACTURER
                ),
                CONF_SERIAL: self._droplet_discovery.properties.get(CONF_SERIAL),
                CONF_SW: self._droplet_discovery.properties.get(CONF_SW),
            }

            return self.async_create_entry(
                title=self._droplet_discovery.device_id,
                data=device_data,
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "device_name": self._droplet_discovery.device_id,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # We should allow this now!!
        return self.async_abort(reason="not_supported")
