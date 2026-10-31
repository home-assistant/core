"""Config flow for the Theben Conexa Smartmeter gateway integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import aiohttp
from probatio import Required, Schema, Secret
from theben_conexa_smgw import ConexaSMGW, checkNetworkConnection

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = Schema(
    {
        Required(CONF_HOST, description={"suggested_value": "192.168.1.200"}): str,
        Required(CONF_USERNAME): str,
        Required(Secret(CONF_PASSWORD)): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = Schema({Required(Secret(CONF_PASSWORD)): str})


class ThebenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Theben Conexa Smartmeter gateway."""

    VERSION = 1

    async def _async_validate_input(
        self, host: str, username: str, password: str, errors: dict[str, str]
    ) -> str | None:
        """Validate the credentials and return the unique id, or fill errors."""
        try:
            await checkNetworkConnection(host)
        except OSError, aiohttp.ClientError:
            errors["base"] = "cannot_connect"
            return None
        try:
            local_api = await ConexaSMGW.create(
                async_get_clientsession(self.hass), host, username, password
            )
        except OSError, aiohttp.ClientError:
            # The smgw unfortunately does not reply with invalid auth it just times out
            # So after we checked that connection is possible we assume Invalid auth if something happens
            errors["base"] = "invalid_auth"
            return None
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return None
        # According to the docs the grid operator can assign multiple users for the
        # same gateway. So we use the combination of smgwID and username as unique id
        return f"{local_api.gatewayInfo.smgwID}-{username}"

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = await self._async_validate_input(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                errors,
            )
            if unique_id is not None:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Smartmeter Gateway", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication upon an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            unique_id = await self._async_validate_input(
                reauth_entry.data[CONF_HOST],
                reauth_entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                errors,
            )
            if unique_id is not None:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "name": reauth_entry.title,
                CONF_HOST: reauth_entry.data[CONF_HOST],
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
            },
        )
