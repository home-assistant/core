"""Config flow for Droplet integration."""

from __future__ import annotations

import logging
from typing import Any

from pydroplet.droplet import DropletDiscovery
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MODEL,
    CONF_PORT,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_DEVICE_NAME,
    CONF_MANUFACTURER,
    CONF_SERIAL,
    CONF_SW,
    DEVICE_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DropletConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Droplet config flow."""

    _droplet_discovery: DropletDiscovery

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
        if not self._droplet_discovery.is_valid():
            return self.async_abort(reason="invalid_discovery_info")

        await self.async_set_unique_id(self._droplet_discovery.device_id)

        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._droplet_discovery.host}
        )

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        errors: dict[str, str] = {}
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
                CONF_CODE: user_input[CONF_CODE],
            }

            # Test if we can connect before returning
            session = async_get_clientsession(self.hass)
            if await self._droplet_discovery.try_connect(
                session, user_input[CONF_CODE]
            ):
                return self.async_create_entry(
                    title=self._droplet_discovery.device_id,
                    data=device_data,
                )
            errors["base"] = "failed_connect"
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CODE): str,
                }
            ),
            description_placeholders={
                "device_name": self._droplet_discovery.device_id,
            },
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_abort(reason="not_supported")
