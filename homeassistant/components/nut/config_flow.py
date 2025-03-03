"""Config flow for Network UPS Tools (NUT) integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aionut import NUTError, NUTLoginError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_ALIAS,
    CONF_BASE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import PyNUTData
from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = {vol.Optional(CONF_USERNAME): str, vol.Optional(CONF_PASSWORD): str}


def _base_schema(nut_config: dict[str, Any]) -> vol.Schema:
    """Generate base schema."""
    base_schema = {
        vol.Optional(CONF_HOST, default=nut_config.get(CONF_HOST) or DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=nut_config.get(CONF_PORT) or DEFAULT_PORT): int,
    }
    base_schema.update(AUTH_SCHEMA)
    return vol.Schema(base_schema)


def _ups_schema(ups_list: dict[str, str]) -> vol.Schema:
    """UPS selection schema."""
    return vol.Schema({vol.Required(CONF_ALIAS): vol.In(ups_list)})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from _base_schema with values provided by the user.
    """

    host = data[CONF_HOST]
    port = data[CONF_PORT]
    alias = data.get(CONF_ALIAS)
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)

    nut_data = PyNUTData(host, port, alias, username, password, persistent=False)
    status = await nut_data.async_update()

    if not alias and not nut_data.ups_list:
        raise AbortFlow("no_ups_found")

    return {"ups_list": nut_data.ups_list, "available_resources": status}


def _format_host_port_alias(user_input: Mapping[str, Any]) -> str:
    """Format a host, port, and alias so it can be used for comparison or display."""
    host = user_input[CONF_HOST]
    port = user_input[CONF_PORT]
    alias = user_input.get(CONF_ALIAS)
    if alias:
        return f"{alias}@{host}:{port}"
    return f"{host}:{port}"


class NutConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Network UPS Tools (NUT)."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the nut config flow."""
        self.nut_config: dict[str, Any] = {}
        self.ups_list: dict[str, str] | None = None
        self.title: str | None = None
        self.reauth_entry: ConfigEntry | None = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a discovered nut device."""
        await self._async_handle_discovery_without_unique_id()
        self.nut_config = {
            CONF_HOST: discovery_info.host or DEFAULT_HOST,
            CONF_PORT: discovery_info.port or DEFAULT_PORT,
        }
        self.context["title_placeholders"] = self.nut_config.copy()
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user input."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        nut_config = self.nut_config
        if user_input is not None:
            nut_config.update(user_input)

            info, errors, placeholders = await self._async_validate_or_error(nut_config)

            if not errors:
                if len(info["ups_list"]) > 1:
                    self.ups_list = info["ups_list"]
                    return await self.async_step_ups()

                if self._host_port_alias_already_configured(nut_config):
                    return self.async_abort(reason="already_configured")
                title = _format_host_port_alias(nut_config)
                return self.async_create_entry(title=title, data=nut_config)

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(nut_config),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_ups(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the picking the ups."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        nut_config = self.nut_config

        if user_input is not None:
            self.nut_config.update(user_input)
            if self._host_port_alias_already_configured(nut_config):
                return self.async_abort(reason="already_configured")
            _, errors, placeholders = await self._async_validate_or_error(nut_config)
            if not errors:
                title = _format_host_port_alias(nut_config)
                return self.async_create_entry(title=title, data=nut_config)

        return self.async_show_form(
            step_id="ups",
            data_schema=_ups_schema(self.ups_list or {}),
            errors=errors,
            description_placeholders=placeholders,
        )

    def _host_port_alias_already_configured(self, user_input: dict[str, Any]) -> bool:
        """See if we already have a nut entry matching user input configured."""
        existing_host_port_aliases = {
            _format_host_port_alias(entry.data)
            for entry in self._async_current_entries()
            if CONF_HOST in entry.data
        }
        return _format_host_port_alias(user_input) in existing_host_port_aliases

    async def _async_validate_or_error(
        self, config: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
        errors: dict[str, str] = {}
        info: dict[str, Any] = {}
        description_placeholders: dict[str, str] = {}
        try:
            info = await validate_input(self.hass, config)
        except NUTLoginError:
            errors[CONF_PASSWORD] = "invalid_auth"
        except NUTError as ex:
            errors[CONF_BASE] = "cannot_connect"
            description_placeholders["error"] = str(ex)
        except AbortFlow:
            raise
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors[CONF_BASE] = "unknown"
        return info, errors, description_placeholders

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        entry_id = self.context["entry_id"]
        self.reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth input."""
        errors: dict[str, str] = {}
        existing_entry = self.reauth_entry
        assert existing_entry
        existing_data = existing_entry.data
        description_placeholders: dict[str, str] = {
            CONF_HOST: existing_data[CONF_HOST],
            CONF_PORT: existing_data[CONF_PORT],
        }
        if user_input is not None:
            new_config = {
                **existing_data,
                # Username/password are optional and some servers
                # use ip based authentication and will fail if
                # username/password are provided
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }
            _, errors, placeholders = await self._async_validate_or_error(new_config)
            if not errors:
                return self.async_update_reload_and_abort(
                    existing_entry, data=new_config
                )
            description_placeholders.update(placeholders)

        return self.async_show_form(
            description_placeholders=description_placeholders,
            step_id="reauth_confirm",
            data_schema=vol.Schema(AUTH_SCHEMA),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for nut."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        base_schema = {
            vol.Optional(CONF_SCAN_INTERVAL, default=scan_interval): vol.All(
                vol.Coerce(int), vol.Clamp(min=10, max=300)
            )
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(base_schema))
