"""Config flow to configure the Android TV integration."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from androidtv import state_detection_rules_validator
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from . import async_connect_androidtv, get_androidtv_mac
from .const import (
    CONF_ADB_SERVER_IP,
    CONF_ADB_SERVER_PORT,
    CONF_ADBKEY,
    CONF_APPS,
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_GET_SOURCES,
    CONF_SCREENCAP,
    CONF_STATE_DETECTION_RULES,
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
    DEFAULT_ADB_SERVER_PORT,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    DEFAULT_GET_SOURCES,
    DEFAULT_PORT,
    DEFAULT_SCREENCAP,
    DEVICE_CLASSES,
    DOMAIN,
    PROP_ETHMAC,
    PROP_WIFIMAC,
)

APPS_NEW_ID = "NewApp"
CONF_APP_DELETE = "app_delete"
CONF_APP_ID = "app_id"
CONF_APP_NAME = "app_name"

RULES_NEW_ID = "NewRule"
CONF_RULE_DELETE = "rule_delete"
CONF_RULE_ID = "rule_id"
CONF_RULE_VALUES = "rule_values"

RESULT_CONN_ERROR = "cannot_connect"
RESULT_UNKNOWN = "unknown"

_LOGGER = logging.getLogger(__name__)


def _is_file(value: str) -> bool:
    """Validate that the value is an existing file."""
    file_in = os.path.expanduser(value)
    return os.path.isfile(file_in) and os.access(file_in, os.R_OK)


class AndroidTVFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @callback
    def _show_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> FlowResult:
        """Show the setup form to the user."""
        host = user_input.get(CONF_HOST, "") if user_input else ""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=host): str,
                vol.Required(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): vol.In(
                    DEVICE_CLASSES
                ),
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            },
        )

        if self.show_advanced_options:
            data_schema = data_schema.extend(
                {
                    vol.Optional(CONF_ADBKEY): str,
                    vol.Optional(CONF_ADB_SERVER_IP): str,
                    vol.Required(
                        CONF_ADB_SERVER_PORT, default=DEFAULT_ADB_SERVER_PORT
                    ): cv.port,
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors={"base": error} if error else None,
        )

    async def _async_check_connection(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Attempt to connect the Android TV."""

        try:
            aftv, error_message = await async_connect_androidtv(self.hass, user_input)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Android TV at %s", user_input[CONF_HOST]
            )
            return RESULT_UNKNOWN, None

        if not aftv:
            _LOGGER.warning(error_message)
            return RESULT_CONN_ERROR, None

        dev_prop = aftv.device_properties
        _LOGGER.info(
            "Android TV at %s: %s = %r, %s = %r",
            user_input[CONF_HOST],
            PROP_ETHMAC,
            dev_prop.get(PROP_ETHMAC),
            PROP_WIFIMAC,
            dev_prop.get(PROP_WIFIMAC),
        )
        unique_id = get_androidtv_mac(dev_prop)
        await aftv.adb_close()
        return None, unique_id

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        error = None

        if user_input is not None:
            host = user_input[CONF_HOST]
            adb_key = user_input.get(CONF_ADBKEY)
            if CONF_ADB_SERVER_IP in user_input:
                if adb_key:
                    return self._show_setup_form(user_input, "key_and_server")
            else:
                user_input.pop(CONF_ADB_SERVER_PORT, None)

            if adb_key:
                if not await self.hass.async_add_executor_job(_is_file, adb_key):
                    return self._show_setup_form(user_input, "adbkey_not_file")

            self._async_abort_entries_match({CONF_HOST: host})
            error, unique_id = await self._async_check_connection(user_input)
            if error is None:
                if not unique_id:
                    return self.async_abort(reason="invalid_unique_id")

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=host,
                    data=user_input,
                )

        return self._show_setup_form(user_input, error)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle an option flow for Android TV."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(config_entry)

        self._apps: dict[str, Any] = self.options.setdefault(CONF_APPS, {})
        self._state_det_rules: dict[str, Any] = self.options.setdefault(
            CONF_STATE_DETECTION_RULES, {}
        )
        self._conf_app_id: str | None = None
        self._conf_rule_id: str | None = None

    @callback
    def _save_config(self, data: dict[str, Any]) -> FlowResult:
        """Save the updated options."""
        new_data = {
            k: v
            for k, v in data.items()
            if k not in [CONF_APPS, CONF_STATE_DETECTION_RULES]
        }
        if self._apps:
            new_data[CONF_APPS] = self._apps
        if self._state_det_rules:
            new_data[CONF_STATE_DETECTION_RULES] = self._state_det_rules

        return self.async_create_entry(title="", data=new_data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            if sel_app := user_input.get(CONF_APPS):
                return await self.async_step_apps(None, sel_app)
            if sel_rule := user_input.get(CONF_STATE_DETECTION_RULES):
                return await self.async_step_rules(None, sel_rule)
            return self._save_config(user_input)

        return self._async_init_form()

    @callback
    def _async_init_form(self) -> FlowResult:
        """Return initial configuration form."""

        apps_list = {k: f"{v} ({k})" if v else k for k, v in self._apps.items()}
        apps = {APPS_NEW_ID: "Add new", **apps_list}
        rules = [RULES_NEW_ID] + list(self._state_det_rules)
        options = self.options

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_APPS): vol.In(apps),
                vol.Optional(
                    CONF_GET_SOURCES,
                    default=options.get(CONF_GET_SOURCES, DEFAULT_GET_SOURCES),
                ): bool,
                vol.Optional(
                    CONF_EXCLUDE_UNNAMED_APPS,
                    default=options.get(
                        CONF_EXCLUDE_UNNAMED_APPS, DEFAULT_EXCLUDE_UNNAMED_APPS
                    ),
                ): bool,
                vol.Optional(
                    CONF_SCREENCAP,
                    default=options.get(CONF_SCREENCAP, DEFAULT_SCREENCAP),
                ): bool,
                vol.Optional(
                    CONF_TURN_OFF_COMMAND,
                    description={
                        "suggested_value": options.get(CONF_TURN_OFF_COMMAND, "")
                    },
                ): str,
                vol.Optional(
                    CONF_TURN_ON_COMMAND,
                    description={
                        "suggested_value": options.get(CONF_TURN_ON_COMMAND, "")
                    },
                ): str,
                vol.Optional(CONF_STATE_DETECTION_RULES): vol.In(rules),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)

    async def async_step_apps(
        self, user_input: dict[str, Any] | None = None, app_id: str | None = None
    ) -> FlowResult:
        """Handle options flow for apps list."""
        if app_id is not None:
            self._conf_app_id = app_id if app_id != APPS_NEW_ID else None
            return self._async_apps_form(app_id)

        if user_input is not None:
            app_id = user_input.get(CONF_APP_ID, self._conf_app_id)
            if app_id:
                if user_input.get(CONF_APP_DELETE, False):
                    self._apps.pop(app_id)
                else:
                    self._apps[app_id] = user_input.get(CONF_APP_NAME, "")

        return await self.async_step_init()

    @callback
    def _async_apps_form(self, app_id: str) -> FlowResult:
        """Return configuration form for apps."""
        app_schema = {
            vol.Optional(
                CONF_APP_NAME,
                description={"suggested_value": self._apps.get(app_id, "")},
            ): str,
        }
        if app_id == APPS_NEW_ID:
            data_schema = vol.Schema({**app_schema, vol.Optional(CONF_APP_ID): str})
        else:
            data_schema = vol.Schema(
                {**app_schema, vol.Optional(CONF_APP_DELETE, default=False): bool}
            )

        return self.async_show_form(
            step_id="apps",
            data_schema=data_schema,
            description_placeholders={
                "app_id": f"`{app_id}`" if app_id != APPS_NEW_ID else "",
            },
        )

    async def async_step_rules(
        self, user_input: dict[str, Any] | None = None, rule_id: str | None = None
    ) -> FlowResult:
        """Handle options flow for detection rules."""
        if rule_id is not None:
            self._conf_rule_id = rule_id if rule_id != RULES_NEW_ID else None
            return self._async_rules_form(rule_id)

        if user_input is not None:
            rule_id = user_input.get(CONF_RULE_ID, self._conf_rule_id)
            if rule_id:
                if user_input.get(CONF_RULE_DELETE, False):
                    self._state_det_rules.pop(rule_id)
                elif str_det_rule := user_input.get(CONF_RULE_VALUES):
                    state_det_rule = _validate_state_det_rules(str_det_rule)
                    if state_det_rule is None:
                        return self._async_rules_form(
                            rule_id=self._conf_rule_id or RULES_NEW_ID,
                            default_id=rule_id,
                            errors={"base": "invalid_det_rules"},
                        )
                    self._state_det_rules[rule_id] = state_det_rule

        return await self.async_step_init()

    @callback
    def _async_rules_form(
        self, rule_id: str, default_id: str = "", errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Return configuration form for detection rules."""
        state_det_rule = self._state_det_rules.get(rule_id)
        str_det_rule = json.dumps(state_det_rule) if state_det_rule else ""

        rule_schema = {vol.Optional(CONF_RULE_VALUES, default=str_det_rule): str}
        if rule_id == RULES_NEW_ID:
            data_schema = vol.Schema(
                {vol.Optional(CONF_RULE_ID, default=default_id): str, **rule_schema}
            )
        else:
            data_schema = vol.Schema(
                {**rule_schema, vol.Optional(CONF_RULE_DELETE, default=False): bool}
            )

        return self.async_show_form(
            step_id="rules",
            data_schema=data_schema,
            description_placeholders={
                "rule_id": f"`{rule_id}`" if rule_id != RULES_NEW_ID else "",
            },
            errors=errors,
        )


def _validate_state_det_rules(state_det_rules: str) -> list[Any] | None:
    """Validate a string that contain state detection rules and return a dict."""
    try:
        json_rules = json.loads(state_det_rules)
    except ValueError:
        _LOGGER.warning("Error loading state detection rules")
        return None

    if not isinstance(json_rules, list):
        json_rules = [json_rules]

    try:
        state_detection_rules_validator(json_rules, ValueError)
    except ValueError as exc:
        _LOGGER.warning("Invalid state detection rules: %s", exc)
        return None
    return json_rules
