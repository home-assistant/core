"""Config flow for Yardian integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from pyyardian import (
    AsyncYardianClient,
    DeviceInfo,
    NetworkException,
    NotAuthorizedException,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PRODUCT_NAME

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(probatio.Secret(CONF_ACCESS_TOKEN)): str,
    }
)


class YardianConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yardian."""

    VERSION = 1

    async def async_fetch_device_info(self, host: str, access_token: str) -> DeviceInfo:
        """Fetch device info from Yardian."""
        yarcli = await AsyncYardianClient.create(
            async_get_clientsession(self.hass),
            host,
            token=access_token,
        )
        return await yarcli.fetch_device_info()

    @override
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
            except NetworkException, TimeoutError:
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication of an existing Yardian device."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate a replacement access token for the existing device."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_info = await self.async_fetch_device_info(
                    entry.data[CONF_HOST], user_input[CONF_ACCESS_TOKEN]
                )
            except NotAuthorizedException:
                errors["base"] = "invalid_auth"
            except NetworkException, TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_info["yid"])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_ACCESS_TOKEN)): str}
            ),
            errors=errors,
        )
