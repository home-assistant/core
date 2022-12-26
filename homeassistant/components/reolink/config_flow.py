"""Config flow for the Reolink camera component."""
from __future__ import annotations

import logging
from typing import cast

from reolink_ip.exceptions import ApiError, CredentialsInvalidError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import CONF_PROTOCOL, CONF_USE_HTTPS, DEFAULT_PROTOCOL, DOMAIN
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)


class ReolinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Reolink options."""

    def __init__(self, config_entry):
        """Initialize ReolinkOptionsFlowHandler."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the Reolink options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROTOCOL,
                        default=self.config_entry.options.get(
                            CONF_PROTOCOL, DEFAULT_PROTOCOL
                        ),
                    ): vol.In(["rtsp", "rtmp"]),
                }
            ),
        )


class ReolinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reolink device."""

    VERSION = 1

    host: ReolinkHost | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ReolinkOptionsFlowHandler:
        """Options callback for Reolink."""
        return ReolinkOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            try:
                await self.async_obtain_host_settings(self.hass, user_input)
            except CannotConnect:
                errors[CONF_HOST] = "cannot_connect"
            except CredentialsInvalidError:
                errors[CONF_HOST] = "invalid_auth"
            except ApiError as err:
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "api_error"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "unknown"

            self.host = cast(ReolinkHost, self.host)

            if not errors:
                user_input[CONF_PORT] = self.host.api.port
                user_input[CONF_USE_HTTPS] = self.host.api.use_https

                await self.async_set_unique_id(
                    self.host.unique_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured(updates=user_input)

                return self.async_create_entry(
                    title=str(self.host.api.nvr_name), data=user_input
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default="admin"): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_HOST): str,
            }
        )
        if errors:
            data_schema = data_schema.extend(
                {
                    vol.Optional(CONF_PORT): cv.positive_int,
                    vol.Optional(CONF_USE_HTTPS): bool,
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_obtain_host_settings(
        self, hass: core.HomeAssistant, user_input: dict
    ):
        """Initialize the Reolink host and get the host information."""
        host = ReolinkHost(hass, user_input, {})

        try:
            if not await host.async_init():
                raise CannotConnect
        finally:
            await host.stop()

        self.host = host


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
