"""Config flow to configure the Android TV integration."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from androidtv import state_detection_rules_validator
from androidtvremote2 import (
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
    SOURCE_REAUTH,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    ObjectSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import async_connect_androidtv, get_androidtv_mac
from .const import (
    CONF_ADB_SERVER_IP,
    CONF_ADB_SERVER_PORT,
    CONF_ADBKEY,
    CONF_APP_ICON,
    CONF_APP_NAME,
    CONF_APPS,
    CONF_CONNECTION_TYPE,
    CONF_ENABLE_IME,
    CONF_ENABLE_IME_DEFAULT_VALUE,
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_GET_SOURCES,
    CONF_SCREENCAP_INTERVAL,
    CONF_STATE_DETECTION_RULES,
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
    CONNECTION_TYPE_ADB,
    CONNECTION_TYPE_REMOTE,
    DEFAULT_ADB_SERVER_PORT,
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    DEFAULT_GET_SOURCES,
    DEFAULT_PORT,
    DEFAULT_SCREENCAP_INTERVAL,
    DEVICE_AUTO,
    DEVICE_CLASSES,
    DOMAIN,
    PROP_ETHMAC,
    PROP_WIFIMAC,
)
from .helpers import create_remote_api

APPS_NEW_ID = "NewApp"
CONF_APP_DELETE = "app_delete"
CONF_APP_ID = "app_id"

RULES_NEW_ID = "NewRule"
CONF_RULE_DELETE = "rule_delete"
CONF_RULE_ID = "rule_id"
CONF_RULE_VALUES = "rule_values"

RESULT_CONN_ERROR = "cannot_connect"
RESULT_UNKNOWN = "unknown"

_EXAMPLE_APP_ID = "com.plexapp.android"
_EXAMPLE_APP_PLAY_STORE_URL = (
    f"https://play.google.com/store/apps/details?id={_EXAMPLE_APP_ID}"
)

STEP_PAIR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("pin"): str,
    }
)

_LOGGER = logging.getLogger(__name__)


def _is_file(value: str) -> bool:
    """Validate that the value is an existing file."""
    file_in = os.path.expanduser(value)
    return os.path.isfile(file_in) and os.access(file_in, os.R_OK)


class AndroidTVFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.host: str = ""
        self.name: str = ""
        self.mac: str = ""
        self.api: Any = None

    @callback
    def _show_adb_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user for ADB connection."""
        host = user_input.get(CONF_HOST, "") if user_input else ""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=host): str,
                vol.Required(CONF_DEVICE_CLASS, default=DEVICE_AUTO): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=k, label=v)
                            for k, v in DEVICE_CLASSES.items()
                        ],
                        translation_key="device_class",
                    )
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
            step_id="adb",
            data_schema=data_schema,
            errors={"base": error} if error else None,
        )

    async def _async_check_adb_connection(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Attempt to connect the Android device via ADB."""

        try:
            aftv, error_message = await async_connect_androidtv(self.hass, user_input)
        except Exception:
            _LOGGER.exception(
                "Unknown error connecting with Android device at %s",
                user_input[CONF_HOST],
            )
            return RESULT_UNKNOWN, None

        if not aftv:
            _LOGGER.warning(error_message)
            return RESULT_CONN_ERROR, None

        dev_prop = aftv.device_properties
        _LOGGER.debug(
            "Android device at %s: %s = %r, %s = %r",
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
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user - show connection type selection."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["adb", "remote"],
        )

    async def async_step_adb(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle ADB connection setup."""
        error = None

        if user_input is not None:
            host = user_input[CONF_HOST]
            adb_key = user_input.get(CONF_ADBKEY)
            if CONF_ADB_SERVER_IP in user_input:
                if adb_key:
                    return self._show_adb_setup_form(user_input, "key_and_server")
            else:
                user_input.pop(CONF_ADB_SERVER_PORT, None)

            if adb_key:
                if not await self.hass.async_add_executor_job(_is_file, adb_key):
                    return self._show_adb_setup_form(user_input, "adbkey_not_file")

            self._async_abort_entries_match({CONF_HOST: host})
            error, unique_id = await self._async_check_adb_connection(user_input)
            if error is None:
                if not unique_id:
                    return self.async_abort(reason="invalid_unique_id")

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                user_input[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_ADB

                return self.async_create_entry(
                    title=host,
                    data=user_input,
                )

        return self._show_adb_setup_form(user_input, error)

    async def async_step_remote(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Remote protocol connection setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]
            api = create_remote_api(self.hass, self.host, enable_ime=False)
            await api.async_generate_cert_if_missing()
            try:
                self.name, self.mac = await api.async_get_name_and_mac()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(format_mac(self.mac))
                self._abort_if_unique_id_configured(updates={CONF_HOST: self.host})
                try:
                    return await self._async_start_pair()
                except (CannotConnect, ConnectionClosed):
                    errors["base"] = "cannot_connect"
        else:
            user_input = {}
        default_host = user_input.get(CONF_HOST, vol.UNDEFINED)
        return self.async_show_form(
            step_id="remote",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=default_host): str}
            ),
            errors=errors,
        )

    async def _async_start_pair(self) -> ConfigFlowResult:
        """Start pairing with the Android TV."""
        self.api = create_remote_api(self.hass, self.host, enable_ime=False)
        await self.api.async_generate_cert_if_missing()
        await self.api.async_start_pairing()
        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pair step for Remote protocol."""
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = user_input["pin"]
            try:
                await self.api.async_finish_pairing(pin)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except ConnectionClosed:
                try:
                    return await self._async_start_pair()
                except (CannotConnect, ConnectionClosed):
                    return self.async_abort(reason="cannot_connect")
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), reload_even_if_entry_is_unchanged=True
                    )

                return self.async_create_entry(
                    title=self.name,
                    data={
                        CONF_HOST: self.host,
                        CONF_NAME: self.name,
                        CONF_MAC: self.mac,
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_REMOTE,
                    },
                )
        return self.async_show_form(
            step_id="pair",
            data_schema=STEP_PAIR_DATA_SCHEMA,
            description_placeholders={CONF_NAME: self.name},
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Android TV device found via zeroconf: %s", discovery_info)
        self.host = discovery_info.host
        self.name = discovery_info.name.removesuffix("._androidtvremote2._tcp.local.")
        if not (mac := discovery_info.properties.get("bt")):
            return self.async_abort(reason="cannot_connect")
        self.mac = mac
        existing_config_entry = await self.async_set_unique_id(format_mac(mac))
        if (
            existing_config_entry
            and CONF_HOST in existing_config_entry.data
            and len(discovery_info.ip_addresses) > 1
        ):
            existing_host = existing_config_entry.data[CONF_HOST]
            if existing_host != self.host:
                if existing_host in [
                    str(ip_address) for ip_address in discovery_info.ip_addresses
                ]:
                    self.host = existing_host
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.host, CONF_NAME: self.name}
        )
        _LOGGER.debug("New Android TV device found via zeroconf: %s", self.name)
        self.context.update({"title_placeholders": {CONF_NAME: self.name}})
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf - show connection type menu."""
        return self.async_show_menu(
            step_id="zeroconf_confirm",
            menu_options=["zeroconf_remote", "zeroconf_adb"],
            description_placeholders={CONF_NAME: self.name},
        )

    async def async_step_zeroconf_remote(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up device discovered via zeroconf using Remote Protocol."""
        try:
            return await self._async_start_pair()
        except (CannotConnect, ConnectionClosed):
            return self.async_abort(reason="cannot_connect")

    async def async_step_zeroconf_adb(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up device discovered via zeroconf using ADB."""
        # Pre-fill the host from zeroconf discovery and go to ADB setup
        if user_input is None:
            user_input = {CONF_HOST: self.host}
        return await self.async_step_adb(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.host = entry_data[CONF_HOST]
        self.name = entry_data[CONF_NAME]
        self.mac = entry_data[CONF_MAC]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._async_start_pair()
            except (CannotConnect, ConnectionClosed):
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_NAME: self.name},
            errors=errors,
        )

    async def async_step_migration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle migration from androidtv_remote integration."""
        if user_input is None:
            return self.async_abort(reason="unknown")

        # Data comes from the migration process in __init__.py
        self.host = user_input[CONF_HOST]
        self.name = user_input[CONF_NAME]
        self.mac = user_input[CONF_MAC]

        await self.async_set_unique_id(format_mac(self.mac))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.name,
            data={
                CONF_HOST: self.host,
                CONF_NAME: self.name,
                CONF_MAC: self.mac,
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_REMOTE,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration for Remote protocol."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]
            api = create_remote_api(self.hass, self.host, enable_ime=False)
            await api.async_generate_cert_if_missing()
            try:
                self.name, self.mac = await api.async_get_name_and_mac()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(format_mac(self.mac))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data={
                        CONF_HOST: self.host,
                        CONF_NAME: self.name,
                        CONF_MAC: self.mac,
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_REMOTE,
                    },
                )
        else:
            user_input = {}
        default_host = self._get_reconfigure_entry().data[CONF_HOST]
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=default_host): str}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        connection_type = config_entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_ADB)
        if connection_type == CONNECTION_TYPE_REMOTE:
            return RemoteOptionsFlowHandler(config_entry)
        return ADBOptionsFlowHandler(config_entry)


class ADBOptionsFlowHandler(OptionsFlow):
    """Handle an option flow for Android Debug Bridge."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._apps: dict[str, Any] = dict(config_entry.options.get(CONF_APPS, {}))
        self._state_det_rules: dict[str, Any] = dict(
            config_entry.options.get(CONF_STATE_DETECTION_RULES, {})
        )
        self._conf_app_id: str | None = None
        self._conf_rule_id: str | None = None

    @callback
    def _save_config(self, data: dict[str, Any]) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            if sel_app := user_input.get(CONF_APPS):
                return await self.async_step_apps(None, sel_app)
            if sel_rule := user_input.get(CONF_STATE_DETECTION_RULES):
                return await self.async_step_rules(None, sel_rule)
            return self._save_config(user_input)

        return self._async_init_form()

    @callback
    def _async_init_form(self) -> ConfigFlowResult:
        """Return initial configuration form."""

        apps_list = {k: f"{v} ({k})" if v else k for k, v in self._apps.items()}
        apps = [SelectOptionDict(value=APPS_NEW_ID, label="Add new")] + [
            SelectOptionDict(value=k, label=v) for k, v in apps_list.items()
        ]
        rules = [RULES_NEW_ID, *self._state_det_rules]
        options = self.config_entry.options

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_APPS): SelectSelector(
                    SelectSelectorConfig(options=apps, mode=SelectSelectorMode.DROPDOWN)
                ),
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
                vol.Required(
                    CONF_SCREENCAP_INTERVAL,
                    default=options.get(
                        CONF_SCREENCAP_INTERVAL, DEFAULT_SCREENCAP_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=15)),
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
                vol.Optional(CONF_STATE_DETECTION_RULES): SelectSelector(
                    SelectSelectorConfig(
                        options=rules, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)

    async def async_step_apps(
        self, user_input: dict[str, Any] | None = None, app_id: str | None = None
    ) -> ConfigFlowResult:
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
    def _async_apps_form(self, app_id: str) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle options flow for detection rules."""
        if rule_id is not None:
            self._conf_rule_id = rule_id if rule_id != RULES_NEW_ID else None
            return self._async_rules_form(rule_id)

        if user_input is not None:
            rule_id = user_input.get(CONF_RULE_ID, self._conf_rule_id)
            if rule_id:
                if user_input.get(CONF_RULE_DELETE, False):
                    self._state_det_rules.pop(rule_id)
                elif det_rule := user_input.get(CONF_RULE_VALUES):
                    state_det_rule = _validate_state_det_rules(det_rule)
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
    ) -> ConfigFlowResult:
        """Return configuration form for detection rules."""
        rule_schema = {
            vol.Optional(
                CONF_RULE_VALUES, default=self._state_det_rules.get(rule_id)
            ): ObjectSelector()
        }
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


class RemoteOptionsFlowHandler(OptionsFlowWithReload):
    """Android TV Remote protocol options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._apps: dict[str, Any] = dict(config_entry.options.get(CONF_APPS, {}))
        self._conf_app_id: str | None = None

    @callback
    def _save_config(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Save the updated options."""
        new_data = {k: v for k, v in data.items() if k not in [CONF_APPS]}
        if self._apps:
            new_data[CONF_APPS] = self._apps

        return self.async_create_entry(title="", data=new_data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            if sel_app := user_input.get(CONF_APPS):
                return await self.async_step_apps(None, sel_app)
            return self._save_config(user_input)

        apps_list = {
            k: f"{v[CONF_APP_NAME]} ({k})" if CONF_APP_NAME in v else k
            for k, v in self._apps.items()
        }
        apps = [SelectOptionDict(value=APPS_NEW_ID, label="Add new")] + [
            SelectOptionDict(value=k, label=v) for k, v in apps_list.items()
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_APPS): SelectSelector(
                        SelectSelectorConfig(
                            options=apps,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="apps",
                        )
                    ),
                    vol.Required(
                        CONF_ENABLE_IME,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_IME, CONF_ENABLE_IME_DEFAULT_VALUE
                        ),
                    ): bool,
                }
            ),
        )

    async def async_step_apps(
        self, user_input: dict[str, Any] | None = None, app_id: str | None = None
    ) -> ConfigFlowResult:
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
                    self._apps[app_id] = {
                        CONF_APP_NAME: user_input.get(CONF_APP_NAME, ""),
                        CONF_APP_ICON: user_input.get(CONF_APP_ICON, ""),
                    }

        return await self.async_step_init()

    @callback
    def _async_apps_form(self, app_id: str) -> ConfigFlowResult:
        """Return configuration form for apps."""

        app_schema = {
            vol.Optional(
                CONF_APP_NAME,
                description={
                    "suggested_value": self._apps[app_id].get(CONF_APP_NAME, "")
                    if app_id in self._apps
                    else ""
                },
            ): str,
            vol.Optional(
                CONF_APP_ICON,
                description={
                    "suggested_value": self._apps[app_id].get(CONF_APP_ICON, "")
                    if app_id in self._apps
                    else ""
                },
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
                "example_app_id": _EXAMPLE_APP_ID,
                "example_app_play_store_url": _EXAMPLE_APP_PLAY_STORE_URL,
            },
        )


def _validate_state_det_rules(state_det_rules: Any) -> list[Any] | None:
    """Validate a string that contain state detection rules and return a dict."""
    json_rules = state_det_rules
    if not isinstance(json_rules, list):
        json_rules = [json_rules]

    try:
        state_detection_rules_validator(json_rules, ValueError)
    except ValueError as exc:
        _LOGGER.warning("Invalid state detection rules: %s", exc)
        return None
    return json_rules
