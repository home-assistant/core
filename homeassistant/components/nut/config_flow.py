"""Config flow for Network UPS Tools (NUT) integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aionut import NUTError, NUTLoginError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ALIAS,
    CONF_BASE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import PyNUTData, _unique_id_from_status
from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

REAUTH_SCHEMA = {vol.Optional(CONF_USERNAME): str, vol.Optional(CONF_PASSWORD): str}

PASSWORD_NOT_CHANGED = "__**password_not_changed**__"


def _base_schema(
    nut_config: Mapping[str, Any],
    use_password_not_changed: bool = False,
) -> vol.Schema:
    """Generate base schema."""
    base_schema = {
        vol.Optional(CONF_HOST, default=nut_config.get(CONF_HOST) or DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=nut_config.get(CONF_PORT) or DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME, default=nut_config.get(CONF_USERNAME) or ""): str,
        vol.Optional(
            CONF_PASSWORD,
            default=PASSWORD_NOT_CHANGED if use_password_not_changed else "",
        ): str,
    }

    return vol.Schema(base_schema)


def _ups_schema(ups_list: dict[str, str]) -> vol.Schema:
    """UPS selection schema."""
    return vol.Schema({vol.Required(CONF_ALIAS): vol.In(ups_list)})


async def validate_input(data: dict[str, Any]) -> dict[str, Any]:
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


def _check_host_port_alias_match(
    first: Mapping[str, Any], second: Mapping[str, Any]
) -> bool:
    """Check if first and second have the same host, port and alias."""

    if first[CONF_HOST] != second[CONF_HOST] or first[CONF_PORT] != second[CONF_PORT]:
        return False

    first_alias = first.get(CONF_ALIAS)
    second_alias = second.get(CONF_ALIAS)
    if (first_alias is None and second_alias is None) or (
        first_alias is not None
        and second_alias is not None
        and first_alias == second_alias
    ):
        return True

    return False


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

                if unique_id := _unique_id_from_status(info["available_resources"]):
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

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
        """Handle selecting the NUT device alias."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        nut_config = self.nut_config

        if user_input is not None:
            self.nut_config.update(user_input)
            if self._host_port_alias_already_configured(nut_config):
                return self.async_abort(reason="already_configured")

            info, errors, placeholders = await self._async_validate_or_error(nut_config)
            if not errors:
                if unique_id := _unique_id_from_status(info["available_resources"]):
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                title = _format_host_port_alias(nut_config)
                return self.async_create_entry(title=title, data=nut_config)

        return self.async_show_form(
            step_id="ups",
            data_schema=_ups_schema(self.ups_list or {}),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""

        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        nut_config = self.nut_config

        if user_input is not None:
            nut_config.update(user_input)

            info, errors, placeholders = await self._async_validate_or_error(nut_config)

            if not errors:
                if len(info["ups_list"]) > 1:
                    self.ups_list = info["ups_list"]
                    return await self.async_step_reconfigure_ups()

                if not _check_host_port_alias_match(
                    reconfigure_entry.data,
                    nut_config,
                ) and (self._host_port_alias_already_configured(nut_config)):
                    return self.async_abort(reason="already_configured")

                if unique_id := _unique_id_from_status(info["available_resources"]):
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_mismatch(reason="unique_id_mismatch")
                if nut_config[CONF_PASSWORD] == PASSWORD_NOT_CHANGED:
                    nut_config.pop(CONF_PASSWORD)

                new_title = _format_host_port_alias(nut_config)
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    unique_id=unique_id,
                    title=new_title,
                    data_updates=nut_config,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_base_schema(
                reconfigure_entry.data,
                use_password_not_changed=True,
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure_ups(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selecting the NUT device alias."""

        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        nut_config = self.nut_config

        if user_input is not None:
            self.nut_config.update(user_input)

            if not _check_host_port_alias_match(
                reconfigure_entry.data,
                nut_config,
            ) and (self._host_port_alias_already_configured(nut_config)):
                return self.async_abort(reason="already_configured")

            info, errors, placeholders = await self._async_validate_or_error(nut_config)
            if not errors:
                if unique_id := _unique_id_from_status(info["available_resources"]):
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_mismatch(reason="unique_id_mismatch")

                if nut_config[CONF_PASSWORD] == PASSWORD_NOT_CHANGED:
                    nut_config.pop(CONF_PASSWORD)

                new_title = _format_host_port_alias(nut_config)
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    unique_id=unique_id,
                    title=new_title,
                    data_updates=nut_config,
                )

        return self.async_show_form(
            step_id="reconfigure_ups",
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
            info = await validate_input(config)
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
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth input."""

        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        reauth_data = reauth_entry.data
        description_placeholders: dict[str, str] = {
            CONF_HOST: reauth_data[CONF_HOST],
            CONF_PORT: reauth_data[CONF_PORT],
        }

        if user_input is not None:
            new_config = {
                **reauth_data,
                # Username/password are optional and some servers
                # use ip based authentication and will fail if
                # username/password are provided
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }
            _, errors, placeholders = await self._async_validate_or_error(new_config)
            if not errors:
                return self.async_update_reload_and_abort(reauth_entry, data=new_config)
            description_placeholders.update(placeholders)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(REAUTH_SCHEMA),
            errors=errors,
            description_placeholders=description_placeholders,
        )
