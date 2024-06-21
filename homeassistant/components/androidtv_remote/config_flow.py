"""Config flow for Android TV Remote integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
)
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_APP_ICON, CONF_APP_NAME, CONF_APPS, CONF_ENABLE_IME, DOMAIN
from .helpers import create_api, get_enable_ime

_LOGGER = logging.getLogger(__name__)

APPS_NEW_ID = "NewApp"
CONF_APP_DELETE = "app_delete"
CONF_APP_ID = "app_id"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
    }
)

STEP_PAIR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("pin"): str,
    }
)


class AndroidTVRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Android TV Remote."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize a new AndroidTVRemoteConfigFlow."""
        self.api: AndroidTVRemote | None = None
        self.reauth_entry: ConfigEntry | None = None
        self.host: str | None = None
        self.name: str | None = None
        self.mac: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.host = user_input["host"]
            assert self.host
            api = create_api(self.hass, self.host, enable_ime=False)
            try:
                await api.async_generate_cert_if_missing()
                self.name, self.mac = await api.async_get_name_and_mac()
                assert self.mac
                await self.async_set_unique_id(format_mac(self.mac))
                self._abort_if_unique_id_configured(updates={CONF_HOST: self.host})
                return await self._async_start_pair()
            except (CannotConnect, ConnectionClosed):
                # Likely invalid IP address or device is network unreachable. Stay
                # in the user step allowing the user to enter a different host.
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_start_pair(self) -> ConfigFlowResult:
        """Start pairing with the Android TV. Navigate to the pair flow to enter the PIN shown on screen."""
        assert self.host
        self.api = create_api(self.hass, self.host, enable_ime=False)
        await self.api.async_generate_cert_if_missing()
        await self.api.async_start_pairing()
        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pair step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                pin = user_input["pin"]
                assert self.api
                await self.api.async_finish_pairing(pin)
                if self.reauth_entry:
                    await self.hass.config_entries.async_reload(
                        self.reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")
                assert self.name
                return self.async_create_entry(
                    title=self.name,
                    data={
                        CONF_HOST: self.host,
                        CONF_NAME: self.name,
                        CONF_MAC: self.mac,
                    },
                )
            except InvalidAuth:
                # Invalid PIN. Stay in the pair step allowing the user to enter
                # a different PIN.
                errors["base"] = "invalid_auth"
            except ConnectionClosed:
                # Either user canceled pairing on the Android TV itself (most common)
                # or device doesn't respond to the specified host (device was unplugged,
                # network was unplugged, or device got a new IP address).
                # Attempt to pair again.
                try:
                    return await self._async_start_pair()
                except (CannotConnect, ConnectionClosed):
                    # Device doesn't respond to the specified host. Abort.
                    # If we are in the user flow we could go back to the user step to allow
                    # them to enter a new IP address but we cannot do that for the zeroconf
                    # flow. Simpler to abort for both flows.
                    return self.async_abort(reason="cannot_connect")
        return self.async_show_form(
            step_id="pair",
            data_schema=STEP_PAIR_DATA_SCHEMA,
            description_placeholders={CONF_NAME: self.name},
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Android TV device found via zeroconf: %s", discovery_info)
        self.host = discovery_info.host
        self.name = discovery_info.name.removesuffix("._androidtvremote2._tcp.local.")
        self.mac = discovery_info.properties.get("bt")
        if not self.mac:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(format_mac(self.mac))
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.host, CONF_NAME: self.name}
        )
        _LOGGER.debug("New Android TV device found via zeroconf: %s", self.name)
        self.context.update({"title_placeholders": {CONF_NAME: self.name}})
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is not None:
            try:
                return await self._async_start_pair()
            except (CannotConnect, ConnectionClosed):
                # Device became network unreachable after discovery.
                # Abort and let discovery find it again later.
                return self.async_abort(reason="cannot_connect")
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={CONF_NAME: self.name},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.host = entry_data[CONF_HOST]
        self.name = entry_data[CONF_NAME]
        self.mac = entry_data[CONF_MAC]
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
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
                # Device is network unreachable. Abort.
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_NAME: self.name},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AndroidTVRemoteOptionsFlowHandler:
        """Create the options flow."""
        return AndroidTVRemoteOptionsFlowHandler(config_entry)


class AndroidTVRemoteOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Android TV Remote options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(config_entry)
        self._apps: dict[str, Any] = self.options.setdefault(CONF_APPS, {})
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
                            options=apps, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(
                        CONF_ENABLE_IME,
                        default=get_enable_ime(self.config_entry),
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
            },
        )
