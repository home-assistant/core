"""Config flow for Matrix integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

from nio import AsyncClient, LoginError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_COMMANDS,
    CONF_EXPRESSION,
    CONF_HOMESERVER,
    CONF_REACTION,
    CONF_ROOMS,
    CONF_ROOMS_REGEX,
    CONF_WORD,
    DEFAULT_HOMESERVER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOMESERVER, default=DEFAULT_HOMESERVER
        ): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
        ),
        vol.Required(CONF_USERNAME): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): selector.BooleanSelector(),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)

_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ROOMS, default=[]): selector.TextSelector(
            selector.TextSelectorConfig(multiple=True)
        ),
        vol.Optional(CONF_COMMANDS): selector.ObjectSelector(),
    }
)


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = AsyncClient(
        homeserver=data[CONF_HOMESERVER],
        user=data[CONF_USERNAME],
        ssl=data[CONF_VERIFY_SSL],
    )
    try:
        login_response = await client.login(data[CONF_PASSWORD])
        if isinstance(login_response, LoginError):
            # Distinguish between auth failures and connection issues
            if login_response.status_code == "M_FORBIDDEN":
                raise InvalidAuth
            raise CannotConnect

        whoami_response = await client.whoami()
        if hasattr(whoami_response, "user_id"):
            user_id = whoami_response.user_id
        else:
            user_id = data[CONF_USERNAME]
    finally:
        await client.close()

    return {"title": user_id, "user_id": user_id}


class MatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Matrix."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MatrixOptionsFlowHandler:
        """Create the options flow."""
        return MatrixOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["user_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        try:
            info = await validate_input(self.hass, import_data)
        except InvalidAuth:
            _LOGGER.debug("Invalid auth while validating imported YAML config")
            return self.async_abort(reason="invalid_auth")
        except CannotConnect:
            _LOGGER.debug("Cannot connect while validating imported YAML config")
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception(
                "Unexpected exception while validating imported YAML config"
            )
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(info["user_id"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=info["title"],
            data=import_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_data = {**reauth_entry.data, **user_input}

            try:
                info = await validate_input(self.hass, reauth_data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                if info["user_id"] != reauth_entry.unique_id:
                    return self.async_abort(reason="wrong_account")

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={
                "username": reauth_entry.data[CONF_USERNAME],
                "homeserver": reauth_entry.data[CONF_HOMESERVER],
            },
        )


class MatrixOptionsFlowHandler(OptionsFlow):
    """Handle Matrix options (rooms and commands)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage rooms and commands."""
        errors: dict[str, str] = {}

        if user_input is not None:
            rooms: list[str] = user_input.get(CONF_ROOMS) or []
            commands = user_input.get(CONF_COMMANDS) or []

            room_re = re.compile(CONF_ROOMS_REGEX)
            for room in rooms:
                if not room_re.match(room):
                    errors[CONF_ROOMS] = "invalid_rooms"
                    break

            if not isinstance(commands, list):
                errors[CONF_COMMANDS] = "invalid_commands"
            else:
                for cmd in commands:
                    if not isinstance(cmd, dict):
                        errors[CONF_COMMANDS] = "invalid_commands"
                        break
                    if not cmd.get(CONF_NAME):
                        errors[CONF_COMMANDS] = "invalid_commands"
                        break
                    triggers = [
                        k
                        for k in (CONF_WORD, CONF_EXPRESSION, CONF_REACTION)
                        if cmd.get(k)
                    ]
                    if len(triggers) != 1:
                        errors[CONF_COMMANDS] = "invalid_commands"
                        break

            if not errors:
                return self.async_create_entry(
                    data={
                        CONF_ROOMS: rooms,
                        CONF_COMMANDS: commands,
                    }
                )

        current_rooms: list[Any] = self.config_entry.options.get(
            CONF_ROOMS, self.config_entry.data.get(CONF_ROOMS, [])
        )
        current_commands: list[Any] = self.config_entry.options.get(
            CONF_COMMANDS, self.config_entry.data.get(CONF_COMMANDS, [])
        )

        serialized_commands = []
        for cmd in current_commands:
            serialized_cmd = dict(cmd)
            if expr := serialized_cmd.get(CONF_EXPRESSION):
                if hasattr(expr, "pattern"):
                    serialized_cmd[CONF_EXPRESSION] = expr.pattern
            serialized_commands.append(serialized_cmd)

        suggested = {
            CONF_ROOMS: current_rooms,
            CONF_COMMANDS: serialized_commands,
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_OPTIONS_SCHEMA, suggested),
            errors=errors,
        )
