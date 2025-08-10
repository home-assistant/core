"""Config flow for Yardian integration."""

from __future__ import annotations

import logging
from typing import Any

from pyyardian import (
    AsyncYardianClient,
    DeviceInfo,
    NetworkException,
    NotAuthorizedException,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PRODUCT_NAME

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
    }
)


class YardianConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yardian."""

    VERSION = 1

    async def async_fetch_device_info(self, host: str, access_token: str) -> DeviceInfo:
        """Fetch device info from Yardian."""
        yarcli = AsyncYardianClient(
            async_get_clientsession(self.hass),
            host,
            access_token,
        )
        return await yarcli.fetch_device_info()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_info = await self.async_fetch_device_info(
                    user_input["host"], user_input["access_token"]
                )
            except NotAuthorizedException:
                errors["base"] = "invalid_auth"
            except NetworkException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_info["yid"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    data=user_input | device_info,
                    title=PRODUCT_NAME,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
