"""Config flow to configure the AsusWrt integration."""

import logging
import os
import socket
from typing import Any, cast, override

from asusrouter import AsusRouterError
import probatio

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .bridge import AsusWrtBridge
from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_MORE_OPTIONS,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    CONF_TRACK_UNKNOWN,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
    MODE_AP,
    MODE_ROUTER,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    PROTOCOL_SSH,
    PROTOCOL_TELNET,
)

ALLOWED_PROTOCOL = [
    PROTOCOL_HTTPS,
    PROTOCOL_SSH,
    PROTOCOL_HTTP,
    PROTOCOL_TELNET,
]

RESULT_CONN_ERROR = "cannot_connect"
RESULT_SUCCESS = "success"
RESULT_UNKNOWN = "unknown"

_LOGGER = logging.getLogger(__name__)

LEGACY_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_MODE, default=MODE_ROUTER): probatio.In(
            {MODE_ROUTER: "Router", MODE_AP: "Access Point"}
        ),
    }
)

RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): str,
        probatio.Required(CONF_MORE_OPTIONS): section(
            probatio.Schema(
                {
                    probatio.Optional(CONF_PORT): probatio.Port(),
                    probatio.Optional(CONF_SSH_KEY): str,
                }
            ),
            SectionConfig(collapsed=True),
        ),
    }
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME.total_seconds()
        ): probatio.All(probatio.Coerce(int), probatio.Clamp(min=0, max=900)),
        probatio.Optional(CONF_TRACK_UNKNOWN, default=DEFAULT_TRACK_UNKNOWN): bool,
    }
)


async def get_options_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """Get options schema."""
    options_flow: SchemaOptionsFlowHandler
    options_flow = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    used_protocol = options_flow.config_entry.data[CONF_PROTOCOL]
    if used_protocol in [PROTOCOL_SSH, PROTOCOL_TELNET]:
        data_schema = OPTIONS_SCHEMA.extend(
            {
                probatio.Required(CONF_INTERFACE, default=DEFAULT_INTERFACE): str,
                probatio.Required(CONF_DNSMASQ, default=DEFAULT_DNSMASQ): str,
            }
        )
        if options_flow.config_entry.data[CONF_MODE] == MODE_AP:
            return data_schema.extend(
                {
                    probatio.Optional(CONF_REQUIRE_IP, default=True): bool,
                }
            )
        return data_schema

    return OPTIONS_SCHEMA


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(get_options_schema),
}


def _is_file(value: str) -> bool:
    """Validate that the value is an existing file."""
    file_in = os.path.expanduser(value)
    return os.path.isfile(file_in) and os.access(file_in, os.R_OK)


def _get_ip(host: str) -> str | None:
    """Get the ip address from the host name."""
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


class AsusWrtFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AsusWRT."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the AsusWrt config flow."""
        self._config_data: dict[str, Any] = {}

    @callback
    def _show_setup_form(self, error: str | None = None) -> ConfigFlowResult:
        """Show the setup form to the user."""

        user_input = self._config_data

        schema = {
            probatio.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
            probatio.Required(
                CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
            ): str,
            probatio.Optional(probatio.Secret(CONF_PASSWORD)): str,
            probatio.Required(
                CONF_PROTOCOL,
                default=user_input.get(CONF_PROTOCOL, PROTOCOL_HTTPS),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=ALLOWED_PROTOCOL, translation_key="protocols"
                )
            ),
            probatio.Required(CONF_MORE_OPTIONS): section(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_PORT): probatio.Port(),
                        probatio.Optional(CONF_SSH_KEY): str,
                    }
                ),
                SectionConfig(collapsed=True),
            ),
        }

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(schema),
            errors={CONF_BASE: error} if error else None,
        )

    async def _async_check_connection(
        self, user_input: dict[str, str | int]
    ) -> tuple[str, str | None]:
        """Attempt to connect the AsusWrt router."""

        api: AsusWrtBridge
        host = user_input[CONF_HOST]
        protocol = user_input[CONF_PROTOCOL]
        error: str | None = None

        conf = {**user_input, CONF_MODE: MODE_ROUTER}
        api = AsusWrtBridge.get_bridge(self.hass, conf)
        try:
            await api.async_connect()

        except AsusRouterError, OSError:
            _LOGGER.error(
                "Error connecting to the AsusWrt router at %s using protocol %s",
                host,
                protocol,
            )
            error = RESULT_CONN_ERROR

        except Exception:
            _LOGGER.exception(
                "Unknown error connecting with AsusWrt router at %s using protocol %s",
                host,
                protocol,
            )
            error = RESULT_UNKNOWN

        if error is None:
            if not api.is_connected:
                _LOGGER.error(
                    "Error connecting to the AsusWrt router at %s using protocol %s",
                    host,
                    protocol,
                )
                error = RESULT_CONN_ERROR

        if error is not None:
            return error, None

        _LOGGER.debug(
            "Successfully connected to the AsusWrt router at %s using protocol %s",
            host,
            protocol,
        )
        unique_id = api.label_mac
        await api.async_disconnect()

        return RESULT_SUCCESS, unique_id

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""

        # if there's one entry without unique ID, we abort config flow
        for unique_id in self._async_current_ids():
            if unique_id is None:
                return self.async_abort(reason="no_unique_id")

        if user_input is None:
            return self._show_setup_form()

        user_input = user_input.copy()
        more_options = user_input.pop(CONF_MORE_OPTIONS, {})
        user_input.update(more_options)

        self._config_data = user_input
        error, unique_id = await self._async_validate_input(user_input)
        if error is not None:
            return self._show_setup_form(error=error)

        if unique_id:
            await self.async_set_unique_id(unique_id)
        # we allow to configure a single instance without unique id
        elif self._async_current_entries():
            return self.async_abort(reason="invalid_unique_id")
        else:
            _LOGGER.warning(
                "This device does not provide a valid Unique ID."
                " Configuration of multiple instance will not be possible"
            )

        if user_input[CONF_PROTOCOL] in [PROTOCOL_SSH, PROTOCOL_TELNET]:
            return await self.async_step_legacy()
        return await self._async_save_entry()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the router connection."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = user_input.copy()
            user_input.update(user_input.pop(CONF_MORE_OPTIONS, {}))
            data = {
                key: value
                for key, value in entry.data.items()
                if key not in (CONF_PASSWORD, CONF_PORT, CONF_SSH_KEY)
            } | user_input
            error, unique_id = await self._async_validate_input(data)
            if error is None:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch()
                # A loaded entry is reloaded by its update listener
                if entry.update_listeners:
                    return self.async_update_and_abort(entry, data=data)
                return self.async_update_reload_and_abort(entry, data=data)
            errors[CONF_BASE] = error
            suggested_values = data
        else:
            suggested_values = dict(entry.data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA,
                {
                    CONF_HOST: suggested_values[CONF_HOST],
                    CONF_USERNAME: suggested_values[CONF_USERNAME],
                    CONF_MORE_OPTIONS: {
                        key: suggested_values[key]
                        for key in (CONF_PORT, CONF_SSH_KEY)
                        if key in suggested_values
                    },
                },
            ),
            errors=errors,
        )

    async def _async_validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Validate the input and return an error or the unique ID."""
        pwd: str | None = user_input.get(CONF_PASSWORD)
        ssh: str | None = user_input.get(CONF_SSH_KEY)
        protocol: str = user_input[CONF_PROTOCOL]

        if not pwd and protocol != PROTOCOL_SSH:
            return "pwd_required", None
        if not (pwd or ssh):
            return "pwd_or_ssh", None
        if pwd and ssh:
            return "pwd_and_ssh", None
        if ssh and not await self.hass.async_add_executor_job(_is_file, ssh):
            return "ssh_not_file", None

        host: str = user_input[CONF_HOST]
        if not await self.hass.async_add_executor_job(_get_ip, host):
            return "invalid_host", None

        result, unique_id = await self._async_check_connection(user_input)
        if result != RESULT_SUCCESS:
            return result, None
        return None, unique_id

    async def async_step_legacy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow for legacy settings."""
        if user_input is None:
            return self.async_show_form(step_id="legacy", data_schema=LEGACY_SCHEMA)

        self._config_data.update(user_input)
        return await self._async_save_entry()

    async def _async_save_entry(self) -> ConfigFlowResult:
        """Save entry data if unique id is valid."""
        return self.async_create_entry(
            title=self._config_data[CONF_HOST],
            data=self._config_data,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
