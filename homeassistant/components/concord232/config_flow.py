"""Config flow for the Concord232 integration."""

import logging
from typing import Any, override

from concord232 import client as concord232_client
import requests
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_MODE, CONF_NAME, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import build_url
from .const import (
    CONF_EXCLUDE_ZONES,
    CONF_IMPORT_PLATFORM,
    CONF_IMPORTED_PLATFORMS,
    CONF_ZONE_TYPES,
    DEFAULT_MODE,
    DEFAULT_PORT,
    DOMAIN,
    MODE_AUDIBLE,
    MODE_SILENT,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CODE): str,
        vol.Required(CONF_MODE, default=DEFAULT_MODE): SelectSelector(
            SelectSelectorConfig(
                options=[MODE_AUDIBLE, MODE_SILENT],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="arm_home_mode",
            )
        ),
    }
)


def _try_connect(url: str) -> bool:
    """Return True when the Concord232 server answers."""
    try:
        concord232_client.Client(url).list_partitions()
    except requests.exceptions.RequestException:
        return False
    return True


class Concord232ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Concord232 config flow."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> Concord232OptionsFlow:
        """Create the options flow."""
        return Concord232OptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            url = build_url(user_input[CONF_HOST], user_input[CONF_PORT])
            if await self.hass.async_add_executor_job(_try_connect, url):
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from YAML platform configuration.

        Concurrent imports are serialized by async_import_yaml, whose lock
        spans the whole flow including entry registration.
        """
        result = await self._async_handle_import(import_data)

        # Scoped per server: several YAML endpoints can import independently
        issue_id = (
            "deprecated_yaml_import_issue_cannot_connect"
            f"_{import_data[CONF_HOST]}_{import_data[CONF_PORT]}"
        )
        if (
            result["type"] is FlowResultType.ABORT
            and result["reason"] == "cannot_connect"
        ):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                breaks_in_ha_version="2027.3.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_cannot_connect",
                translation_placeholders={
                    "host": str(import_data[CONF_HOST]),
                    "port": str(import_data[CONF_PORT]),
                },
            )
            return result

        # This server imports now; drop the failure issue a previous attempt left
        ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        ir.async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2027.3.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Concord232",
            },
        )
        return result

    async def _async_handle_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create or enrich the config entry for imported YAML configuration."""
        data: dict[str, Any] = {
            CONF_HOST: import_data[CONF_HOST],
            CONF_PORT: import_data[CONF_PORT],
        }
        # Restrict the entry to the platform(s) the YAML actually configured
        if platform := import_data.get(CONF_IMPORT_PLATFORM):
            data[CONF_IMPORTED_PLATFORMS] = [platform]
        options: dict[str, Any] = {}
        if CONF_CODE in import_data:
            options[CONF_CODE] = import_data[CONF_CODE]
        if CONF_MODE in import_data:
            options[CONF_MODE] = import_data[CONF_MODE]
        if import_data.get(CONF_EXCLUDE_ZONES):
            options[CONF_EXCLUDE_ZONES] = import_data[CONF_EXCLUDE_ZONES]
        if import_data.get(CONF_ZONE_TYPES):
            # JSON storage requires string keys
            options[CONF_ZONE_TYPES] = {
                str(number): zone_type
                for number, zone_type in import_data[CONF_ZONE_TYPES].items()
            }

        # Both platforms import the same YAML server. When the other platform's
        # import created the entry first, merge the alarm-only fields (code,
        # mode, name) into it instead of dropping them. YAML only fills gaps:
        # it must never overwrite a user-created entry, options changed later
        # in the UI, or a customized title.
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.data.get(CONF_HOST) != data[CONF_HOST]
                or entry.data.get(CONF_PORT) != data[CONF_PORT]
            ):
                continue
            if entry.source == SOURCE_IMPORT:
                merged_options = {**options, **entry.options}
                title = entry.title
                if CONF_NAME in import_data and title == entry.data[CONF_HOST]:
                    title = import_data[CONF_NAME]
                # The companion platform's import extends the platform set;
                # updating data reloads the entry so the platform loads now.
                # Never narrow an unrestricted entry, only extend a restriction.
                entry_data = dict(entry.data)
                imported = entry_data.get(CONF_IMPORTED_PLATFORMS, [])
                if platform and imported and platform not in imported:
                    entry_data[CONF_IMPORTED_PLATFORMS] = [*imported, platform]
                self.hass.config_entries.async_update_entry(
                    entry, data=entry_data, options=merged_options, title=title
                )
            return self.async_abort(reason="already_configured")

        url = build_url(data[CONF_HOST], data[CONF_PORT])
        if not await self.hass.async_add_executor_job(_try_connect, url):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=import_data.get(CONF_NAME, data[CONF_HOST]),
            data=data,
            options=options,
        )


class Concord232OptionsFlow(OptionsFlow):
    """Handle Concord232 options (arm code and arm-home mode)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Keep the YAML-imported zone settings, which this form does not
            # expose. A cleared code is stored as an explicit empty string so
            # a later YAML import does not treat it as a gap to fill.
            options = {**user_input}
            options.setdefault(CONF_CODE, "")
            for key in (CONF_EXCLUDE_ZONES, CONF_ZONE_TYPES):
                if key in self.config_entry.options:
                    options[key] = self.config_entry.options[key]
            return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, dict(self.config_entry.options)
            ),
        )
