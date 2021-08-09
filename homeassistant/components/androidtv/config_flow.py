"""Config flow to configure the Android TV integration."""
import logging
import os
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from . import async_connect_androidtv, validate_state_det_rules
from .const import (
    CONF_ADB_KEY,
    CONF_ADB_SERVER_IP,
    CONF_ADB_SERVER_PORT,
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
)

APPS_NEW_ID = "NewApp"
CONF_APP_ID = "app_id"
CONF_APP_NAME = "app_name"
CONF_APP_DELETE = "app_delete"

RESULT_CONN_ERROR = "cannot_connect"
RESULT_UNKNOWN = "unknown"
RESULT_SUCCESS = "success"

_LOGGER = logging.getLogger(__name__)


def _is_file(value):
    """Validate that the value is an existing file."""
    file_in = os.path.expanduser(str(value))

    if not os.path.isfile(file_in):
        return False
    if not os.access(file_in, os.R_OK):
        return False
    return True


def _get_ip(host):
    """Get the ip address from the host name."""
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


class AndroidTVFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize Android TV config flow."""
        self._host = None
        self._unique_id = None

    @callback
    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS
                    ): vol.In(DEVICE_CLASSES),
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Optional(CONF_ADB_KEY): str,
                    vol.Optional(CONF_ADB_SERVER_IP): str,
                    vol.Required(
                        CONF_ADB_SERVER_PORT, default=DEFAULT_ADB_SERVER_PORT
                    ): cv.port,
                }
            ),
            errors=errors or {},
        )

    async def _async_check_connection(self, user_input):
        """Attempt to connect the Android TV."""

        try:
            aftv = await async_connect_androidtv(self.hass, user_input, timeout=30.0)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Android TV at %s", self._host
            )
            return RESULT_UNKNOWN

        if not aftv:
            return RESULT_CONN_ERROR

        self._unique_id = aftv.device_properties.get("serialno")
        await aftv.adb_close()
        return RESULT_SUCCESS

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form(user_input)

        errors = {}
        self._unique_id = None
        self._host = user_input[CONF_HOST]
        adb_key = user_input.get(CONF_ADB_KEY)
        adb_server = user_input.get(CONF_ADB_SERVER_IP)

        if adb_key and adb_server:
            errors["base"] = "key_and_server"
        elif adb_key:
            isfile = await self.hass.async_add_executor_job(_is_file, adb_key)
            if not isfile:
                errors["base"] = "adbkey_not_file"

        if not errors:
            ip_address = await self.hass.async_add_executor_job(_get_ip, self._host)
            if not ip_address:
                errors["base"] = "invalid_host"

        if not errors:
            result = await self._async_check_connection(user_input)
            if result != RESULT_SUCCESS:
                errors["base"] = result

        if errors:
            return self._show_setup_form(user_input, errors)

        if not self._unique_id:
            return self.async_abort(reason="invalid_unique_id")
        await self.async_set_unique_id(self._unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._host,
            data=user_input,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Android TV."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._apps = config_entry.options.get(CONF_APPS, {})
        self._conf_app_id = None

    def _save_config(self, data):
        """Save the updated options."""
        for param in [
            CONF_TURN_OFF_COMMAND,
            CONF_TURN_ON_COMMAND,
            CONF_STATE_DETECTION_RULES,
        ]:
            value = data.get(param)
            if value is not None:
                value = value.strip()
                if not value:
                    data.pop(param)

        state_det_rules = data.get(CONF_STATE_DETECTION_RULES)
        if state_det_rules:
            json_rules = validate_state_det_rules(state_det_rules)
            if not json_rules:
                return self._async_init_form(errors={"base": "invalid_det_rules"})

        data[CONF_APPS] = self._apps
        return self.async_create_entry(title="", data=data)

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            sel_app = user_input.get(CONF_APPS)
            if sel_app:
                return await self.async_step_apps(None, sel_app)
            return self._save_config(user_input)

        return self._async_init_form()

    @callback
    def _async_init_form(self, errors=None):
        """Return initial configuration form."""

        apps = {APPS_NEW_ID: "Add new"}
        apps.update(self._apps)
        data_schema = vol.Schema(
            {
                vol.Optional(CONF_APPS): vol.In(apps),
                vol.Optional(
                    CONF_GET_SOURCES,
                    default=self.config_entry.options.get(
                        CONF_GET_SOURCES, DEFAULT_GET_SOURCES
                    ),
                ): bool,
                vol.Optional(
                    CONF_EXCLUDE_UNNAMED_APPS,
                    default=self.config_entry.options.get(
                        CONF_EXCLUDE_UNNAMED_APPS, DEFAULT_EXCLUDE_UNNAMED_APPS
                    ),
                ): bool,
                vol.Optional(
                    CONF_SCREENCAP,
                    default=self.config_entry.options.get(
                        CONF_SCREENCAP, DEFAULT_SCREENCAP
                    ),
                ): bool,
                vol.Optional(
                    CONF_TURN_OFF_COMMAND,
                    default=self.config_entry.options.get(CONF_TURN_OFF_COMMAND, ""),
                ): str,
                vol.Optional(
                    CONF_TURN_ON_COMMAND,
                    default=self.config_entry.options.get(CONF_TURN_ON_COMMAND, ""),
                ): str,
                vol.Optional(
                    CONF_STATE_DETECTION_RULES,
                    default=self.config_entry.options.get(
                        CONF_STATE_DETECTION_RULES, ""
                    ),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )

    async def async_step_apps(self, user_input=None, app_id=None):
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
                    self._apps[app_id] = user_input[CONF_APP_NAME]

        return await self.async_step_init()

    @callback
    def _async_apps_form(self, app_id):
        """Return configuration form for apps."""
        data_schema = vol.Schema(
            {
                vol.Optional(CONF_APP_NAME, default=self._apps.get(app_id, "")): str,
            }
        )
        if app_id == APPS_NEW_ID:
            data_schema = data_schema.extend(
                {
                    vol.Optional(CONF_APP_ID): str,
                }
            )
        else:
            data_schema = data_schema.extend(
                {
                    vol.Optional(CONF_APP_DELETE, default=False): bool,
                }
            )

        return self.async_show_form(
            step_id="apps",
            data_schema=data_schema,
            description_placeholders={
                "app_id": f"`{app_id}`" if app_id != APPS_NEW_ID else "",
            },
        )
