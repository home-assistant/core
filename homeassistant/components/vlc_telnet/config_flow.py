"""Config flow for VLC media player Telnet integration."""
from __future__ import annotations

import logging
from typing import Any

from python_telnet_vlc import ConnectionError as ConnErr, VLCTelnet
from python_telnet_vlc.vlctelnet import AuthError
import voluptuous as vol

from homeassistant import core, exceptions
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def user_form_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Return user form schema."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(
                CONF_HOST, default=user_input.get(CONF_HOST, "localhost")
            ): str,
            vol.Optional(
                CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
            ): int,
            vol.Optional(
                CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
            ): str,
        }
    )


STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


def vlc_connect(vlc: VLCTelnet) -> None:
    """Connect to VLC."""
    vlc.connect()
    vlc.login()
    vlc.disconnect()


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    vlc = VLCTelnet(
        host=data[CONF_HOST],
        password=data[CONF_PASSWORD],
        port=data[CONF_PORT],
        connect=False,
        login=False,
    )

    try:
        await hass.async_add_executor_job(vlc_connect, vlc)
    except (ConnErr, EOFError) as err:
        raise CannotConnect from err
    except AuthError as err:
        raise InvalidAuth from err

    return {"title": data[CONF_NAME]}


class VLCTelnetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VLC media player Telnet."""

    VERSION = 1
    entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=user_form_schema(user_input)
            )

        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=user_form_schema(user_input), errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle the import step."""
        return await self.async_step_user(user_input)

    async def async_step_reauth(self, data: dict[str, Any]) -> FlowResult:
        """Handle reauth flow."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert self.entry
        self.context["title_placeholders"] = {"host": self.entry.data[CONF_HOST]}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirm."""
        assert self.entry
        errors = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, {**self.entry.data, **user_input})
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_HOST: self.entry.data[CONF_HOST]},
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
