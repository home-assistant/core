"""Config flow for VLC media player Telnet integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiovlc.client import Client
from aiovlc.exceptions import AuthError, ConnectError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import DEFAULT_PORT, DOMAIN

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
        }
    )


STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def vlc_connect(vlc: Client) -> None:
    """Connect to VLC."""
    await vlc.connect()
    await vlc.login()
    await vlc.disconnect()


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    vlc = Client(
        password=data[CONF_PASSWORD],
        host=data[CONF_HOST],
        port=data[CONF_PORT],
    )

    try:
        await vlc_connect(vlc)
    except ConnectError as err:
        raise CannotConnect from err
    except AuthError as err:
        raise InvalidAuth from err

    # CONF_NAME is only present in the imported YAML data.
    return {"title": data.get(CONF_NAME) or data[CONF_HOST]}


class VLCTelnetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VLC media player Telnet."""

    VERSION = 1
    hassio_discovery: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=user_form_schema(user_input), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        self.context["title_placeholders"] = {"host": entry_data[CONF_HOST]}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirm."""
        errors = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await validate_input(self.hass, {**reauth_entry.data, **user_input})
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_HOST: reauth_entry.data[CONF_HOST]},
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle the discovery step via hassio."""
        await self.async_set_unique_id("hassio")
        self._abort_if_unique_id_configured(discovery_info.config)

        self.hassio_discovery = discovery_info.config
        self.context["title_placeholders"] = {"host": discovery_info.config[CONF_HOST]}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Supervisor discovery."""
        assert self.hassio_discovery
        if user_input is None:
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={"addon": self.hassio_discovery["addon"]},
            )

        self.hassio_discovery.pop("addon")

        try:
            info = await validate_input(self.hass, self.hassio_discovery)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(title=info["title"], data=self.hassio_discovery)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
