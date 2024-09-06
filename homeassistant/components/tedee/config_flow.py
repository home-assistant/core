"""Config flow for Tedee integration."""

from collections.abc import Mapping
import logging
from typing import Any

from pytedee_async import (
    TedeeAuthException,
    TedeeClient,
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
)
import voluptuous as vol

from homeassistant.components.webhook import async_generate_id as webhook_generate_id
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_WEBHOOK_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCAL_ACCESS_TOKEN, DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class TedeeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tedee."""

    VERSION = 1
    MINOR_VERSION = 2

    reauth_entry: ConfigEntry | None = None
    reconfigure_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if self.reauth_entry:
                host = self.reauth_entry.data[CONF_HOST]
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
                if self.reauth_entry:
                    return self.async_update_reload_and_abort(
                        self.reauth_entry,
                        data={**self.reauth_entry.data, **user_input},
                        reason="reauth_successful",
                    )
                if self.reconfigure_entry:
                    return self.async_update_reload_and_abort(
                        self.reconfigure_entry,
                        data={**self.reconfigure_entry.data, **user_input},
                        reason="reconfigure_successful",
                    )
                await self.async_set_unique_id(local_bridge.serial)
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
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        assert self.reauth_entry

        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_LOCAL_ACCESS_TOKEN,
                            default=self.reauth_entry.data[CONF_LOCAL_ACCESS_TOKEN],
                        ): str,
                    }
                ),
            )
        return await self.async_step_user(user_input)

    async def async_step_reconfigure(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform a reconfiguration."""
        self.reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add reconfigure step to allow to reconfigure a config entry."""
        assert self.reconfigure_entry

        if not user_input:
            return self.async_show_form(
                step_id="reconfigure_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_HOST, default=self.reconfigure_entry.data[CONF_HOST]
                        ): str,
                        vol.Required(
                            CONF_LOCAL_ACCESS_TOKEN,
                            default=self.reconfigure_entry.data[
                                CONF_LOCAL_ACCESS_TOKEN
                            ],
                        ): str,
                    }
                ),
            )
        return await self.async_step_user(user_input)
