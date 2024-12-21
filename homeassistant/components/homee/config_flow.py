"""Config flow for homee integration."""

import logging
from typing import Any, cast

from pyHomee import (
    Homee,
    HomeeAuthFailedException as HomeeAuthenticationFailedException,
    HomeeConnectionFailedException,
)
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from . import HomeeConfigEntry
from .const import (
    CONF_ADD_HOMEE_DATA,
    CONF_DOOR_GROUPS,
    CONF_GROUPS,
    CONF_WINDOW_GROUPS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(
            CONF_ADD_HOMEE_DATA,
        ): bool,
    }
)


async def _get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Init the first step of the options flow."""
    entry = cast(SchemaOptionsFlowHandler, handler.parent_handler).config_entry
    homee: Homee = entry.runtime_data.homee
    groups_selection = {str(g.id): f"{g.name} ({len(g.nodes)})" for g in homee.groups}

    return vol.Schema(
        {
            vol.Required(
                CONF_WINDOW_GROUPS,
                default=entry.options[CONF_GROUPS][CONF_WINDOW_GROUPS],
            ): cv.multi_select(groups_selection),
            vol.Required(
                CONF_DOOR_GROUPS,
                default=entry.options[CONF_GROUPS][CONF_DOOR_GROUPS],
            ): cv.multi_select(groups_selection),
            vol.Required(
                CONF_ADD_HOMEE_DATA,
                default=entry.options[CONF_ADD_HOMEE_DATA],
            ): bool,
        }
    )


OPTIONS_FLOW = {"init": SchemaFlowFormStep(_get_options_schema)}


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

    VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: HomeeConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    def __init__(self) -> None:
        """Initialize the config flow."""
        # self.homee_host: str = None
        # self.homee_id: str = None
        self.homee: Homee = None
        self.all_devices: bool = True
        self.debug_data: bool = False

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial user step."""

        errors = {}
        if user_input is not None:
            try:
                self.homee = await validate_and_connect(self.hass, user_input)
                await self.async_set_unique_id(self.homee.settings.uid)
                self._abort_if_unique_id_configured()
                _LOGGER.info(
                    "Created new homee entry with ID %s", self.homee.settings.uid
                )
                self.debug_data = user_input[CONF_ADD_HOMEE_DATA]
                return await self.async_step_groups()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AbortFlow:
                return self.async_abort(reason="already_configured")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_groups(self, user_input=None) -> ConfigFlowResult:
        """Configure groups options."""
        groups_selection = {
            str(g.id): f"{g.name} ({len(g.nodes)})" for g in self.homee.groups
        }

        # There doesn't seem to be a way to disable a field - so we need 2 separate versions.
        GROUPS_SCHEMA = vol.Schema(
            {
                vol.Required(
                    CONF_WINDOW_GROUPS,
                    default=[],
                ): cv.multi_select(groups_selection),
                vol.Required(
                    CONF_DOOR_GROUPS,
                    default=[],
                ): cv.multi_select(groups_selection),
            }
        )

        if user_input is not None:
            return self.async_create_entry(
                title=f"{self.homee.settings.uid} ({self.homee.host})",
                data={
                    CONF_HOST: self.homee.host,
                    CONF_USERNAME: self.homee.user,
                    CONF_PASSWORD: self.homee.password,
                },
                options={
                    CONF_ADD_HOMEE_DATA: self.debug_data,
                    CONF_GROUPS: user_input,
                },
            )

        return self.async_show_form(step_id="groups", data_schema=GROUPS_SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure flow."""
        errors = {}
        reconfigure_entry = self._get_reconfigure_entry()
        data = reconfigure_entry.data.copy()
        options = reconfigure_entry.options.copy()
        suggested_values = {
            CONF_HOST: data.get(CONF_HOST),
            CONF_USERNAME: data.get(CONF_USERNAME),
            CONF_PASSWORD: data.get(CONF_PASSWORD),
            CONF_ADD_HOMEE_DATA: options[CONF_ADD_HOMEE_DATA],
        }

        if user_input:
            try:
                self.homee = await validate_and_connect(self.hass, user_input)
                await self.async_set_unique_id(self.homee.settings.uid)

                data[CONF_HOST] = user_input.get(CONF_HOST)
                data[CONF_USERNAME] = user_input.get(CONF_USERNAME)
                data[CONF_PASSWORD] = user_input.get(CONF_PASSWORD)
                options[CONF_ADD_HOMEE_DATA] = user_input.get(CONF_ADD_HOMEE_DATA)

                _LOGGER.info("Updated homee entry with ID %s", self.homee.settings.uid)
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data=data, options=options
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                AUTH_SCHEMA, suggested_values
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
