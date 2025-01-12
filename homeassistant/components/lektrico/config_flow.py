"""Config flow for Lektrico Charging Station."""

from __future__ import annotations

from typing import Any

from lektricowifi import Device, DeviceConnectionError
import voluptuous as vol

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    ATTR_HW_VERSION,
    ATTR_SERIAL_NUMBER,
    CONF_HOST,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class LektricoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Lektrico config flow."""

    VERSION = 1

    _host: str
    _name: str
    _serial_number: str
    _board_revision: str
    _device_type: str

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = None

        if user_input is not None:
            self._host = user_input[CONF_HOST]

            # obtain serial number
            try:
                await self._get_lektrico_device_settings_and_treat_unique_id()
                return self._async_create_entry()
            except DeviceConnectionError:
                errors = {CONF_HOST: "cannot_connect"}

        return self._async_show_setup_form(user_input=user_input, errors=errors)

    @callback
    def _async_show_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        schema = self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors or {},
        )

    @callback
    def _async_create_entry(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._host,
                ATTR_SERIAL_NUMBER: self._serial_number,
                CONF_TYPE: self._device_type,
                ATTR_HW_VERSION: self._board_revision,
            },
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host  # 192.168.100.11

        # read settings from the device
        try:
            await self._get_lektrico_device_settings_and_treat_unique_id()
        except DeviceConnectionError:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {
            "serial_number": self._serial_number,
            "name": self._name,
        }

        return await self.async_step_confirm()

    async def _get_lektrico_device_settings_and_treat_unique_id(self) -> None:
        """Get device's serial number from a Lektrico device."""
        device = Device(
            _host=self._host,
            asyncClient=get_async_client(self.hass),
        )

        settings = await device.device_config()
        self._serial_number = str(settings["serial_number"])
        self._device_type = settings["type"]
        self._board_revision = settings["board_revision"]
        self._name = f"{settings['type']}_{self._serial_number}"

        # Check if already configured
        # Set unique id
        await self.async_set_unique_id(self._serial_number, raise_on_progress=True)
        # Abort if already configured, but update the last-known host
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host}, reload_on_update=True
        )

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""

        if user_input is not None:
            return self._async_create_entry()

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")
