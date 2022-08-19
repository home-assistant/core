"""Config flow to configure the FRITZ!Box Tools integration."""
from __future__ import annotations

from collections.abc import Mapping
import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import ParseResult, urlparse

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_OLD_DISCOVERY,
    DEFAULT_CONF_OLD_DISCOVERY,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_AUTH_INVALID,
    ERROR_CANNOT_CONNECT,
    ERROR_UNKNOWN,
    ERROR_UPNP_NOT_CONFIGURED,
)

_LOGGER = logging.getLogger(__name__)


class FritzBoxToolsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a FRITZ!Box Tools config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return FritzBoxToolsOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize FRITZ!Box Tools flow."""
        self._host: str | None = None
        self._entry: ConfigEntry | None = None
        self._name: str = ""
        self._password: str = ""
        self._port: int | None = None
        self._username: str = ""
        self._model: str = ""

    def fritz_tools_init(self) -> str | None:
        """Initialize FRITZ!Box Tools class."""

        try:
            connection = FritzConnection(
                address=self._host,
                port=self._port,
                user=self._username,
                password=self._password,
                timeout=60.0,
                pool_maxsize=30,
            )
        except FritzSecurityError:
            return ERROR_AUTH_INVALID
        except FritzConnectionException:
            return ERROR_CANNOT_CONNECT
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return ERROR_UNKNOWN

        self._model = connection.call_action("DeviceInfo:1", "GetInfo")["NewModelName"]

        if (
            "X_AVM-DE_UPnP1" in connection.services
            and not connection.call_action("X_AVM-DE_UPnP1", "GetInfo")["NewEnable"]
        ):
            return ERROR_UPNP_NOT_CONFIGURED

        return None

    async def async_check_configured_entry(self) -> ConfigEntry | None:
        """Check if entry is configured."""
        assert self._host
        current_host = await self.hass.async_add_executor_job(
            socket.gethostbyname, self._host
        )

        for entry in self._async_current_entries(include_ignore=False):
            entry_host = await self.hass.async_add_executor_job(
                socket.gethostbyname, entry.data[CONF_HOST]
            )
            if entry_host == current_host:
                return entry
        return None

    @callback
    def _async_create_entry(self) -> FlowResult:
        """Async create flow handler entry."""
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._host,
                CONF_PASSWORD: self._password,
                CONF_PORT: self._port,
                CONF_USERNAME: self._username,
            },
            options={
                CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME.total_seconds(),
                CONF_OLD_DISCOVERY: DEFAULT_CONF_OLD_DISCOVERY,
            },
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a flow initialized by discovery."""
        ssdp_location: ParseResult = urlparse(discovery_info.ssdp_location or "")
        self._host = ssdp_location.hostname
        self._port = ssdp_location.port
        self._name = (
            discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or discovery_info.upnp[ssdp.ATTR_UPNP_MODEL_NAME]
        )
        self.context[CONF_HOST] = self._host

        if not self._host or ipaddress.ip_address(self._host).is_link_local:
            return self.async_abort(reason="ignore_ip6_link_local")

        if uuid := discovery_info.upnp.get(ssdp.ATTR_UPNP_UDN):
            if uuid.startswith("uuid:"):
                uuid = uuid[5:]
            await self.async_set_unique_id(uuid)
            self._abort_if_unique_id_configured({CONF_HOST: self._host})

        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self._host:
                return self.async_abort(reason="already_in_progress")

        if entry := await self.async_check_configured_entry():
            if uuid and not entry.unique_id:
                self.hass.config_entries.async_update_entry(entry, unique_id=uuid)
            return self.async_abort(reason="already_configured")

        self.context.update(
            {
                "title_placeholders": {"name": self._name.replace("FRITZ!Box ", "")},
                "configuration_url": f"http://{self._host}",
            }
        )

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is None:
            return self._show_setup_form_confirm()

        errors = {}

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        error = await self.hass.async_add_executor_job(self.fritz_tools_init)

        if error:
            errors["base"] = error
            return self._show_setup_form_confirm(errors)

        return self._async_create_entry()

    def _show_setup_form_init(self, errors: dict[str, str] | None = None) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors or {},
        )

    def _show_setup_form_confirm(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"name": self._name},
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form_init()
        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]
        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        if not (error := await self.hass.async_add_executor_job(self.fritz_tools_init)):
            self._name = self._model

            if await self.async_check_configured_entry():
                error = "already_configured"

        if error:
            return self._show_setup_form_init({"base": error})

        return self._async_create_entry()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle flow upon an API authentication error."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._host = entry_data[CONF_HOST]
        self._port = entry_data[CONF_PORT]
        self._username = entry_data[CONF_USERNAME]
        self._password = entry_data[CONF_PASSWORD]
        return await self.async_step_reauth_confirm()

    def _show_setup_form_reauth_confirm(
        self, user_input: dict[str, Any], errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the reauth form to the user."""
        default_username = user_input.get(CONF_USERNAME)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=default_username): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"host": self._host},
            errors=errors or {},
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self._show_setup_form_reauth_confirm(
                user_input={CONF_USERNAME: self._username}
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        if error := await self.hass.async_add_executor_job(self.fritz_tools_init):
            return self._show_setup_form_reauth_confirm(
                user_input=user_input, errors={"base": error}
            )

        assert isinstance(self._entry, ConfigEntry)
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={
                CONF_HOST: self._host,
                CONF_PASSWORD: self._password,
                CONF_PORT: self._port,
                CONF_USERNAME: self._username,
            },
        )
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        return self.async_abort(reason="reauth_successful")


class FritzBoxToolsOptionsFlowHandler(OptionsFlow):
    """Handle a option flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CONSIDER_HOME,
                    default=self.config_entry.options.get(
                        CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
                    ),
                ): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=900)),
                vol.Optional(
                    CONF_OLD_DISCOVERY,
                    default=self.config_entry.options.get(
                        CONF_OLD_DISCOVERY, DEFAULT_CONF_OLD_DISCOVERY
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
