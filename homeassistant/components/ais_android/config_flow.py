"""Config flow to configure the AIS Android integration."""
import asyncio
import logging
import os
import socket

from adb_shell.auth.keygen import keygen
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ais_dom import ais_global
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.storage import STORAGE_DIR

from . import async_connect_androidtv, validate_state_det_rules
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
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    DEFAULT_GET_SOURCES,
    DEFAULT_PORT,
    DEFAULT_SCREENCAP,
    DEVICE_ANDROIDTV,
    DEVICE_CLASSES,
    DOMAIN,
    PROP_ETHMAC,
    PROP_WIFIMAC,
)

APPS_NEW_ID = "NewApp"
CONF_APP_DELETE = "app_delete"
CONF_APP_ID = "app_id"
CONF_APP_NAME = "app_name"

RESULT_CONN_ERROR = "cannot_connect"
RESULT_UNKNOWN = "unknown"

_LOGGER = logging.getLogger(__name__)


def _is_file(value):
    """Validate that the value is an existing file."""
    file_in = os.path.expanduser(str(value))
    return os.path.isfile(file_in) and os.access(file_in, os.R_OK)


def _get_ip(host):
    """Get the ip address from the host name."""
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


class AndroidTVFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @callback
    def _show_setup_form(self, user_input=None, error=None):
        """Show the setup form to the user."""
        user_input = user_input or {}
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=user_input.get(CONF_HOST, "127.0.0.1")
                ): str,
                vol.Required(CONF_DEVICE_CLASS, default="ais"): vol.In(DEVICE_CLASSES),
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
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
            step_id="user", data_schema=data_schema, errors={"base": error}
        )

    async def _async_check_connection(self, user_input):
        """Attempt to connect the Android TV."""

        try:
            aftv = await async_connect_androidtv(self.hass, user_input)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Android TV at %s", user_input[CONF_HOST]
            )
            return RESULT_UNKNOWN, None

        if not aftv:
            return RESULT_CONN_ERROR, None

        dev_prop = aftv.device_properties
        unique_id = format_mac(
            dev_prop.get(PROP_ETHMAC) or dev_prop.get(PROP_WIFIMAC, "")
        )
        await aftv.adb_close()
        return None, unique_id

    async def async_execute_command(self, cmd):
        cmd_process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await cmd_process.communicate()

        if stdout:
            _LOGGER.info("stdout %s", stdout.decode())
        if stderr:
            _LOGGER.info("stderr %s", stderr.decode())

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        error = None

        if user_input is not None:
            host = user_input[CONF_HOST]
            adb_key = user_input.get(CONF_ADBKEY)
            adb_server = user_input.get(CONF_ADB_SERVER_IP)

            if adb_key and adb_server:
                return self._show_setup_form(user_input, "key_and_server")

            if adb_key:
                isfile = await self.hass.async_add_executor_job(_is_file, adb_key)
                if not isfile:
                    return self._show_setup_form(user_input, "adbkey_not_file")

            ip_address = await self.hass.async_add_executor_job(_get_ip, host)
            if not ip_address:
                return self._show_setup_form(user_input, "invalid_host")

            self._async_abort_entries_match({CONF_HOST: host})
            if ip_address != host:
                self._async_abort_entries_match({CONF_HOST: ip_address})

            device_calss = user_input.get(CONF_DEVICE_CLASS)
            if device_calss == "ais":
                user_input[CONF_DEVICE_CLASS] = DEVICE_ANDROIDTV
                if host == "127.0.0.1" and ais_global.has_root():
                    await self.async_execute_command(
                        "su -c 'setprop persist.service.adb.enable 1'"
                    )
                    await self.async_execute_command(
                        "su -c 'setprop service.adb.tcp.port 5555'"
                    )
                    await self.async_execute_command("su -c 'stop adbd'")
                    await self.async_execute_command(
                        "su -c 'touch /data/misc/adb/adb_keys'"
                    )
                    adbkey = self.hass.config.path(STORAGE_DIR, "androidtv_adbkey")
                    if not os.path.isfile(adbkey):
                        # Generate ADB key files
                        keygen(adbkey)
                    await self.async_execute_command(
                        "su -c 'rm /data/misc/adb/adb_keys'"
                    )
                    await self.async_execute_command(
                        "su -c 'cat /data/data/pl.sviete.dom/files/home/AIS/.storage/androidtv_adbkey.pub >> "
                        "/data/misc/adb/adb_keys'"
                    )
                    # TODO add without rm
                    # await self.async_execute_command(
                    #     "su -c 'grep  -F -f /data/data/pl.sviete.dom/files/home/AIS"
                    #     "/.storage/androidtv_adbkey.pub /data/misc/adb/adb_keys || cat "
                    #     "/data/data/pl.sviete.dom/files/home/AIS/.storage"
                    #     "/androidtv_adbkey.pub >> /data/misc/adb/adb_keys'"
                    # )
                    await self.async_execute_command(
                        "su -c 'chmod 0644 /data/misc/adb/adb_keys'"
                    )
                    await self.async_execute_command("su -c 'start adbd'")

            error, unique_id = await self._async_check_connection(user_input)
            if error is None:
                if not unique_id:
                    return self.async_abort(reason="invalid_unique_id")

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or host, data=user_input
                )

        user_input = user_input or {}
        return self._show_setup_form(user_input, error)

    async def async_step_import(self, import_config=None):
        """Import a config entry."""
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == import_config[CONF_HOST]:
                _LOGGER.warning(
                    "Already configured. This yaml configuration has already been imported. Please remove it"
                )
                return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an option flow for Android TV."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._apps = config_entry.options.get(CONF_APPS, {})
        self._conf_app_id = None

    def _save_config(self, data):
        """Save the updated options."""
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

        apps = {APPS_NEW_ID: "Dodaj nową aplikację"}
        apps.update(self._apps)
        options = self.config_entry.options
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
                vol.Optional(
                    CONF_STATE_DETECTION_RULES,
                    description={
                        "suggested_value": options.get(CONF_STATE_DETECTION_RULES, "")
                    },
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
                    self._apps[app_id] = user_input.get(CONF_APP_NAME, "")

        return await self.async_step_init()

    @callback
    def _async_apps_form(self, app_id):
        """Return configuration form for apps."""
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_APP_NAME,
                    description={"suggested_value": self._apps.get(app_id, "")},
                ): str
            }
        )
        if app_id == APPS_NEW_ID:
            data_schema = data_schema.extend({vol.Optional(CONF_APP_ID): str})
        else:
            data_schema = data_schema.extend(
                {vol.Optional(CONF_APP_DELETE, default=False): bool}
            )

        return self.async_show_form(
            step_id="apps",
            data_schema=data_schema,
            description_placeholders={
                "app_id": f"`{app_id}`" if app_id != APPS_NEW_ID else ""
            },
        )
