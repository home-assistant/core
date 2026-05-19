"""Config flow for Cast."""

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_UUID
from homeassistant.core import callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_IGNORE_CEC, CONF_KNOWN_HOSTS, DOMAIN

if TYPE_CHECKING:
    from . import CastConfigEntry

CONF_MORE_OPTIONS = "more_options"
IGNORE_CEC_SCHEMA = vol.Schema(vol.All(cv.ensure_list, [cv.string]))
KNOWN_HOSTS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_KNOWN_HOSTS,
        ): SelectSelector(
            SelectSelectorConfig(custom_value=True, options=[], multiple=True),
        )
    }
)
OPTIONS_SCHEMA = KNOWN_HOSTS_SCHEMA.extend(
    {
        vol.Required(CONF_MORE_OPTIONS): section(
            vol.Schema(
                {
                    vol.Optional(CONF_UUID): str,
                    vol.Optional(CONF_IGNORE_CEC): str,
                }
            ),
            SectionConfig(collapsed=True),
        )
    }
)
WANTED_UUID_SCHEMA = vol.Schema(vol.All(cv.ensure_list, [cv.string]))


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: CastConfigEntry,
    ) -> CastOptionsFlowHandler:
        """Get the options flow for this handler."""
        return CastOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_config()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        await self.async_set_unique_id(DOMAIN)

        return await self.async_step_confirm()

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if user_input is not None:
            known_hosts = _trim_items(user_input.get(CONF_KNOWN_HOSTS, []))
            return self.async_create_entry(
                title="Google Cast",
                data=self._get_data(known_hosts=known_hosts),
            )

        return self.async_show_form(step_id="config", data_schema=KNOWN_HOSTS_SCHEMA)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(title="Google Cast", data=self._get_data())

        return self.async_show_form(step_id="confirm")

    def _get_data(
        self, *, known_hosts: list[str] | None = None
    ) -> dict[str, list[str]]:
        return {
            CONF_IGNORE_CEC: [],
            CONF_KNOWN_HOSTS: known_hosts or [],
            CONF_UUID: [],
        }


class CastOptionsFlowHandler(OptionsFlow):
    """Handle Google Cast options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Google Cast options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            bad_cec, ignore_cec = _string_to_list(
                user_input[CONF_MORE_OPTIONS].get(CONF_IGNORE_CEC, ""),
                IGNORE_CEC_SCHEMA,
            )
            bad_uuid, wanted_uuid = _string_to_list(
                user_input[CONF_MORE_OPTIONS].get(CONF_UUID, ""), WANTED_UUID_SCHEMA
            )
            if not bad_cec and not bad_uuid:
                known_hosts = _trim_items(user_input.get(CONF_KNOWN_HOSTS, []))
                updated_config = dict(self.config_entry.data)
                updated_config[CONF_IGNORE_CEC] = ignore_cec
                updated_config[CONF_KNOWN_HOSTS] = known_hosts
                updated_config[CONF_UUID] = wanted_uuid

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=updated_config
                )
                return self.async_create_entry(title="", data={})
            suggested: dict[str, Any] = user_input
        else:
            suggested = {CONF_MORE_OPTIONS: {}}
            if CONF_KNOWN_HOSTS in self.config_entry.data:
                suggested[CONF_KNOWN_HOSTS] = self.config_entry.data[CONF_KNOWN_HOSTS]
            for key in (CONF_UUID, CONF_IGNORE_CEC):
                if key not in self.config_entry.data:
                    continue
                suggested[CONF_MORE_OPTIONS][key] = _list_to_string(
                    self.config_entry.data[key]
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, suggested),
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


def _trim_items(items: list[str]) -> list[str]:
    return [x.strip() for x in items if x.strip()]
