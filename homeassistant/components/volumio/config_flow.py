"""Config flow for Volumio integration."""
from __future__ import annotations

import logging
from typing import Any

from pyvolumio import CannotConnectError, Volumio
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CONN_ERROR_ASSUMES_OFF, DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=3000): int,
        vol.Required(CONF_CONN_ERROR_ASSUMES_OFF, default=False): bool,
    }
)


async def validate_input(hass, host, port):
    """Validate the user input allows us to connect."""
    volumio = Volumio(host, port, async_get_clientsession(hass))

    try:
        return await volumio.get_system_info()
    except CannotConnectError as error:
        raise CannotConnect from error


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Volumio."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._port: int | None = None
        self._name: str | None = None
        self._conn_error_assumes_off: bool | None = None
        self._uuid: str | None = None

    @callback
    def _async_get_entry(self):
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_NAME: self._name,
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_CONN_ERROR_ASSUMES_OFF: self._conn_error_assumes_off,
                CONF_ID: self._uuid,
            },
        )

    async def _set_uid_and_abort(self):
        await self.async_set_unique_id(self._uuid)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_NAME: self._name,
                CONF_CONN_ERROR_ASSUMES_OFF: self._conn_error_assumes_off,
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            info = None
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._conn_error_assumes_off = user_input[CONF_CONN_ERROR_ASSUMES_OFF]
            try:
                info = await validate_input(self.hass, self._host, self._port)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if info is not None:
                self._name = info.get("name", self._host)
                self._uuid = info.get("id")
                if self._uuid is not None:
                    await self._set_uid_and_abort()

                return self._async_get_entry()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host
        self._port = discovery_info.port
        self._name = discovery_info.properties["volumioName"]
        self._uuid = discovery_info.properties["UUID"]
        self._conn_error_assumes_off = False

        await self._set_uid_and_abort()

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            try:
                await validate_input(self.hass, self._host, self._port)
                return self._async_get_entry()
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name}
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Allow user to provide options."""
        return VolumioOptionsFlowHandler(config_entry)


class VolumioOptionsFlowHandler(config_entries.OptionsFlow):
    """OptionFlow for Volumio."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow for Volumio."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options for Volumio."""
        if user_input is not None:
            merged_config_entry = self.config_entry.data.copy()
            if CONF_CONN_ERROR_ASSUMES_OFF in user_input:
                merged_config_entry[CONF_CONN_ERROR_ASSUMES_OFF] = user_input[
                    CONF_CONN_ERROR_ASSUMES_OFF
                ]

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=merged_config_entry,
                options=self.config_entry.options,
            )

            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONN_ERROR_ASSUMES_OFF,
                        default=self.config_entry.options.get(
                            CONF_CONN_ERROR_ASSUMES_OFF, False
                        ),
                    ): bool
                }
            ),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
