"""Config flow for homee integration."""

import logging
from typing import Any

from pyHomee import (
    Homee,
    HomeeAuthFailedException as HomeeAuthenticationFailedException,
    HomeeConnectionFailedException,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HomeeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for homee."""

    VERSION = 1

    homee: Homee

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""

        errors = {}
        if user_input is not None:
            self.homee = Homee(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            try:
                await self.homee.get_access_token()
            except HomeeConnectionFailedException:
                errors["base"] = "cannot_connect"
            except HomeeAuthenticationFailedException:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                _LOGGER.info("Got access token for homee")
                self.hass.loop.create_task(self.homee.run())
                _LOGGER.debug("Homee task created")
                await self.homee.wait_until_connected()
                _LOGGER.info("Homee connected")
                self.homee.disconnect()
                _LOGGER.debug("Homee disconnecting")
                await self.homee.wait_until_disconnected()
                _LOGGER.info("Homee config successfully tested")

                await self.async_set_unique_id(self.homee.settings.uid)

                self._abort_if_unique_id_configured()

                _LOGGER.info(
                    "Created new homee entry with ID %s", self.homee.settings.uid
                )

                return self.async_create_entry(
                    title=f"{self.homee.settings.homee_name} ({self.homee.host})",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )
