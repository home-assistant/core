"""Config flow for Cast."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import onboarding, zeroconf
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_UUID
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import CONF_IGNORE_CEC, CONF_KNOWN_HOSTS, DOMAIN

IGNORE_CEC_SCHEMA = vol.Schema(vol.All(cv.ensure_list, [cv.string]))
KNOWN_HOSTS_SCHEMA = vol.Schema(vol.All(cv.ensure_list, [cv.string]))
WANTED_UUID_SCHEMA = vol.Schema(vol.All(cv.ensure_list, [cv.string]))


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._ignore_cec = set[str]()
        self._known_hosts = set[str]()
        self._wanted_uuid = set[str]()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CastOptionsFlowHandler:
        """Get the options flow for this handler."""
        return CastOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_config()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(DOMAIN)

        return await self.async_step_confirm()

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        errors = {}
        data = {CONF_KNOWN_HOSTS: self._known_hosts}

        if user_input is not None:
            bad_hosts = False
            known_hosts = user_input[CONF_KNOWN_HOSTS]
            known_hosts = [x.strip() for x in known_hosts.split(",") if x.strip()]
            try:
                known_hosts = KNOWN_HOSTS_SCHEMA(known_hosts)
            except vol.Invalid:
                errors["base"] = "invalid_known_hosts"
                bad_hosts = True
            else:
                self._known_hosts = known_hosts
                data = self._get_data()
            if not bad_hosts:
                return self.async_create_entry(title="Google Cast", data=data)

        fields = {}
        fields[vol.Optional(CONF_KNOWN_HOSTS, default="")] = str

        return self.async_show_form(
            step_id="config", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""

        data = self._get_data()

        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(title="Google Cast", data=data)

        return self.async_show_form(step_id="confirm")

    def _get_data(self):
        return {
            CONF_IGNORE_CEC: list(self._ignore_cec),
            CONF_KNOWN_HOSTS: list(self._known_hosts),
            CONF_UUID: list(self._wanted_uuid),
        }


class CastOptionsFlowHandler(OptionsFlow):
    """Handle Google Cast options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Google Cast options flow."""
        self.config_entry = config_entry
        self.updated_config: dict[str, Any] = {}

    async def async_step_init(self, user_input: None = None) -> ConfigFlowResult:
        """Manage the Google Cast options."""
        return await self.async_step_basic_options()

    async def async_step_basic_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Google Cast options."""
        errors: dict[str, str] = {}
        current_config = self.config_entry.data
        if user_input is not None:
            bad_hosts, known_hosts = _string_to_list(
                user_input.get(CONF_KNOWN_HOSTS, ""), KNOWN_HOSTS_SCHEMA
            )

            if not bad_hosts:
                self.updated_config = dict(current_config)
                self.updated_config[CONF_KNOWN_HOSTS] = known_hosts

                if self.show_advanced_options:
                    return await self.async_step_advanced_options()

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=self.updated_config
                )
                return self.async_create_entry(title="", data={})

        fields: dict[vol.Marker, type[str]] = {}
        suggested_value = _list_to_string(current_config.get(CONF_KNOWN_HOSTS))
        _add_with_suggestion(fields, CONF_KNOWN_HOSTS, suggested_value)

        return self.async_show_form(
            step_id="basic_options",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=not self.show_advanced_options,
        )

    async def async_step_advanced_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Google Cast options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            bad_cec, ignore_cec = _string_to_list(
                user_input.get(CONF_IGNORE_CEC, ""), IGNORE_CEC_SCHEMA
            )
            bad_uuid, wanted_uuid = _string_to_list(
                user_input.get(CONF_UUID, ""), WANTED_UUID_SCHEMA
            )

            if not bad_cec and not bad_uuid:
                self.updated_config[CONF_IGNORE_CEC] = ignore_cec
                self.updated_config[CONF_UUID] = wanted_uuid
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=self.updated_config
                )
                return self.async_create_entry(title="", data={})

        fields: dict[vol.Marker, type[str]] = {}
        current_config = self.config_entry.data
        suggested_value = _list_to_string(current_config.get(CONF_UUID))
        _add_with_suggestion(fields, CONF_UUID, suggested_value)
        suggested_value = _list_to_string(current_config.get(CONF_IGNORE_CEC))
        _add_with_suggestion(fields, CONF_IGNORE_CEC, suggested_value)

        return self.async_show_form(
            step_id="advanced_options",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=True,
        )


def _list_to_string(items):
    comma_separated_string = ""
    if items:
        comma_separated_string = ",".join(items)
    return comma_separated_string


def _string_to_list(string, schema):
    invalid = False
    items = [x.strip() for x in string.split(",") if x.strip()]
    try:
        items = schema(items)
    except vol.Invalid:
        invalid = True

    return invalid, items


def _add_with_suggestion(
    fields: dict[vol.Marker, type[str]], key: str, suggested_value: str
) -> None:
    fields[vol.Optional(key, description={"suggested_value": suggested_value})] = str
