"""Config flow for Tedee integration."""

from collections.abc import Mapping
import logging
from typing import Any

from aiotedee import (
    TedeeAuthException,
    TedeeClient,
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
)
import voluptuous as vol

from homeassistant.components.webhook import async_generate_id as webhook_generate_id
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_WEBHOOK_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCAL_ACCESS_TOKEN, DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class TedeeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tedee."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if self.source == SOURCE_REAUTH:
                host = self._get_reauth_entry().data[CONF_HOST]
            else:
                host = user_input[CONF_HOST]
            local_access_token = user_input[CONF_LOCAL_ACCESS_TOKEN]
            tedee_client = TedeeClient(
                local_token=local_access_token,
                local_ip=host,
                session=async_get_clientsession(self.hass),
            )
            try:
                local_bridge = await tedee_client.get_local_bridge()
            except (TedeeAuthException, TedeeLocalAuthException):
                errors[CONF_LOCAL_ACCESS_TOKEN] = "invalid_api_key"
            except TedeeClientException:
                errors[CONF_HOST] = "invalid_host"
            except TedeeDataUpdateException as exc:
                _LOGGER.error("Error during local bridge discovery: %s", exc)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(local_bridge.serial)
                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=user_input
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=NAME,
                    data={**user_input, CONF_WEBHOOK_ID: webhook_generate_id()},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                    ): str,
                    vol.Required(
                        CONF_LOCAL_ACCESS_TOKEN,
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_LOCAL_ACCESS_TOKEN,
                            default=self._get_reauth_entry().data[
                                CONF_LOCAL_ACCESS_TOKEN
                            ],
                        ): str,
                    }
                ),
            )
        return await self.async_step_user(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Perform a reconfiguration."""
        if not user_input:
            reconfigure_entry = self._get_reconfigure_entry()
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_HOST, default=reconfigure_entry.data[CONF_HOST]
                        ): str,
                        vol.Required(
                            CONF_LOCAL_ACCESS_TOKEN,
                            default=reconfigure_entry.data[CONF_LOCAL_ACCESS_TOKEN],
                        ): str,
                    }
                ),
            )
        return await self.async_step_user(user_input)
