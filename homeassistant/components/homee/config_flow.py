"""Config flow for homee integration."""

import logging
from typing import Any

from pyHomee import (
    Homee,
    HomeeAuthFailedException as HomeeAuthenticationFailedException,
    HomeeConnectionFailedException,
)
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow

from .const import CONF_ADD_HOMEE_DATA, DOMAIN

_LOGGER = logging.getLogger(__name__)

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(
            CONF_ADD_HOMEE_DATA,
        ): bool,
    }
)


async def validate_and_connect(hass: core.HomeAssistant, data) -> Homee:
    """Validate the user input allows us to connect."""

    # Create a Homee object and try to receive an access token.
    # This tells us if the host is reachable and if the credentials work
    homee = Homee(data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])

    try:
        await homee.get_access_token()
        _LOGGER.info("Got access token for homee")
    except HomeeAuthenticationFailedException as exc:
        _LOGGER.warning("Authentication to Homee failed: %s", exc.reason)
        raise InvalidAuth from exc
    except HomeeConnectionFailedException as exc:
        _LOGGER.warning("Connection to Homee failed: %s", exc.__cause__)
        raise CannotConnect from exc

    hass.loop.create_task(homee.run())
    _LOGGER.info("Homee task created")
    await homee.wait_until_connected()
    _LOGGER.info("Homee connected")
    homee.disconnect()
    _LOGGER.info("Homee disconnecting")
    await homee.wait_until_disconnected()
    _LOGGER.info("Homee config successfully tested")
    # Return homee instance
    return homee


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for homee."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.homee: Homee = None
        self.all_devices: bool = True
        self.debug_data: bool = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""

        errors = {}
        if user_input is not None:
            try:
                self.homee = await validate_and_connect(self.hass, user_input)
                self._abort_if_unique_id_configured()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AbortFlow:
                return self.async_abort(reason="already_configured")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(self.homee.settings.uid)
                _LOGGER.info(
                    "Created new homee entry with ID %s", self.homee.settings.uid
                )

                return self.async_create_entry(
                    title=f"{self.homee.settings.uid} ({self.homee.host})",
                    data={
                        CONF_HOST: self.homee.host,
                        CONF_USERNAME: self.homee.user,
                        CONF_PASSWORD: self.homee.password,
                    },
                    options={CONF_ADD_HOMEE_DATA: user_input[CONF_ADD_HOMEE_DATA]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=BASE_SCHEMA,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
