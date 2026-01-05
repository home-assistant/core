"""Config flow for devolo Home Network integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceNotFound, DevicePasswordProtected
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, PRODUCT, SERIAL_NUMBER, TITLE
from .coordinator import DevoloHomeNetworkConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_IP_ADDRESS): str, vol.Optional(CONF_PASSWORD): str}
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Optional(CONF_PASSWORD): str})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    zeroconf_instance = await zeroconf.async_get_instance(hass)
    async_client = get_async_client(hass)

    device = Device(data[CONF_IP_ADDRESS], zeroconf_instance=zeroconf_instance)

    device.password = data[CONF_PASSWORD]

    await device.async_connect(session_instance=async_client)

    # Try a password protected, non-writing device API call that raises, if the password is wrong.
    # If only the plcnet API is available, we can continue without trying a password as the plcnet
    # API does not require a password.
    if device.device:
        await device.device.async_uptime()

    await device.async_disconnect()

    return {
        SERIAL_NUMBER: str(device.serial_number),
        TITLE: device.hostname.split(".", maxsplit=1)[0],
    }


class DevoloHomeNetworkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for devolo Home Network."""

    VERSION = 1

    host: str
    _reauth_entry: DevoloHomeNetworkConfigEntry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except DeviceNotFound:
                errors["base"] = "cannot_connect"
            except DevicePasswordProtected:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    info[SERIAL_NUMBER], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info[TITLE], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        if discovery_info.properties["MT"] in ["2600", "2601"]:
            return self.async_abort(reason="home_control")

        await self.async_set_unique_id(discovery_info.properties["SN"])
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: discovery_info.host}
        )

        self.host = discovery_info.host
        self.context["title_placeholders"] = {
            PRODUCT: discovery_info.properties["Product"],
            CONF_NAME: discovery_info.hostname.split(".")[0],
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        title = self.context["title_placeholders"][CONF_NAME]
        errors: dict = {}
        data_schema: vol.Schema | None = None

        if user_input is not None:
            data = {
                CONF_IP_ADDRESS: self.host,
                CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
            }
            try:
                await validate_input(self.hass, data)
            except DevicePasswordProtected:
                errors = {"base": "invalid_auth"}
                data_schema = STEP_REAUTH_DATA_SCHEMA
            else:
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=data_schema,
            description_placeholders={"host_name": title},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._reauth_entry = self._get_reauth_entry()
        self.host = entry_data[CONF_IP_ADDRESS]
        placeholders = {
            **self.context["title_placeholders"],
            PRODUCT: self._reauth_entry.runtime_data.device.product,
        }
        self.context["title_placeholders"] = placeholders
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by reauthentication."""
        errors: dict = {}
        if user_input is not None:
            data = {
                CONF_IP_ADDRESS: self.host,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                await validate_input(self.hass, data)
            except DevicePasswordProtected:
                errors = {"base": "invalid_auth"}
            else:
                return self.async_update_reload_and_abort(self._reauth_entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )
