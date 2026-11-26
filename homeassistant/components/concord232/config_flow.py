"""Config flow for the Concord232 integration."""

import logging
from typing import Any, override

from concord232 import client as concord232_client
import probatio
import requests

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
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.hass_dict import HassKey

from . import build_url
from .const import (
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DEFAULT_MODE,
    DEFAULT_PORT,
    DOMAIN,
    MODE_AUDIBLE,
    MODE_SILENT,
)

_LOGGER = logging.getLogger(__name__)

DATA_IMPORTED_ALARMS: HassKey[set[tuple[str, int]]] = HassKey(
    f"{DOMAIN}_imported_alarms"
)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
    }
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_CODE): str,
        probatio.Required(CONF_MODE, default=DEFAULT_MODE): SelectSelector(
            SelectSelectorConfig(
                options=[MODE_AUDIBLE, MODE_SILENT],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="arm_home_mode",
            )
        ),
    }
)


def _normalize_host(host: str) -> str:
    """Return the host in the form config entries store and match on."""
    host = host.strip().lower().removeprefix("http://").rstrip("/.")
    # yarl adds the brackets of an IPv6 literal itself
    return host.removeprefix("[").removesuffix("]")


def _try_connect(host: str, port: int) -> str | None:
    """Return an error key, or None when a Concord232 server answers."""
    try:
        url = build_url(host, port)
    except ValueError:
        return "invalid_host"
    try:
        concord232_client.Client(url).list_partitions()
    # KeyError, TypeError: the host answered with JSON that is not concord232's
    except requests.exceptions.RequestException, KeyError, TypeError:
        return "cannot_connect"
    return None


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
            data = {
                CONF_HOST: _normalize_host(user_input[CONF_HOST]),
                CONF_PORT: user_input[CONF_PORT],
            }
            self._async_abort_entries_match(data)
            error = await self.hass.async_add_executor_job(
                _try_connect, data[CONF_HOST], data[CONF_PORT]
            )
            if error is None:
                return self.async_create_entry(title=data[CONF_HOST], data=data)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from YAML platform configuration."""
        host = _normalize_host(import_data[CONF_HOST])
        port: int = import_data[CONF_PORT]
        result = await self._async_handle_import(host, port, import_data)

        # Scoped per server: several YAML endpoints can import independently
        issue_id = f"deprecated_yaml_import_issue_cannot_connect_{host}_{port}"
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
                translation_placeholders={"host": host, "port": str(port)},
            )
            return result

        if CONF_NAME in import_data:
            self.hass.data.setdefault(DATA_IMPORTED_ALARMS, set()).add((host, port))
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
        self, host: str, port: int, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create or update the config entry for imported YAML configuration."""
        # Only the alarm platform's YAML carries a name
        if CONF_NAME in import_data and (host, port) in self.hass.data.get(
            DATA_IMPORTED_ALARMS, ()
        ):
            _LOGGER.warning(
                "Ignoring YAML alarm control panel %s: the Concord232 server "
                "at %s:%s is already configured by another YAML alarm "
                "control panel and only one panel per server is supported",
                import_data[CONF_NAME],
                host,
                port,
            )
            return self.async_abort(reason="already_configured")

        options: dict[str, Any] = {
            key: import_data[key]
            for key in (CONF_CODE, CONF_MODE)
            if key in import_data
        }
        if import_data.get(CONF_EXCLUDE_ZONES):
            options[CONF_EXCLUDE_ZONES] = import_data[CONF_EXCLUDE_ZONES]
        if import_data.get(CONF_ZONE_TYPES):
            # JSON storage requires string keys
            options[CONF_ZONE_TYPES] = {
                str(number): zone_type
                for number, zone_type in import_data[CONF_ZONE_TYPES].items()
            }

        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] != host or entry.data[CONF_PORT] != port:
                continue
            # YAML never changes an entry created in the UI
            if entry.source == SOURCE_IMPORT:
                # Code, mode and title only fill gaps: the UI can change them
                merged_options = {**options, **entry.options}
                # Zone options have no UI, so the sensor YAML stays authoritative
                for key in (CONF_EXCLUDE_ZONES, CONF_ZONE_TYPES):
                    if key not in import_data:
                        continue
                    merged_options.pop(key, None)
                    if key in options:
                        merged_options[key] = options[key]
                title = entry.title
                if CONF_NAME in import_data and title == entry.data[CONF_HOST]:
                    title = import_data[CONF_NAME]
                self.hass.config_entries.async_update_entry(
                    entry, options=merged_options, title=title
                )
            return self.async_abort(reason="already_configured")

        if await self.hass.async_add_executor_job(_try_connect, host, port):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=import_data.get(CONF_NAME, host),
            data={CONF_HOST: host, CONF_PORT: port},
            options=options,
        )


class Concord232OptionsFlow(OptionsFlow):
    """Handle Concord232 options (arm code and arm-home mode)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            options = {**user_input}
            # An explicit "" keeps a later YAML import from refilling a cleared code
            options.setdefault(CONF_CODE, "")
            # Zone options come from YAML only; this form does not expose them
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
