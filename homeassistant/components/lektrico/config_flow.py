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
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class LektricoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Lektrico config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str
        self._friendly_name: str
        self._serial_number: str
        self._board_revision: str
        self._device_type: str

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._async_show_setup_form()

        self._host = user_input[CONF_HOST]
        self._friendly_name = user_input[CONF_FRIENDLY_NAME]

        # obtain serial number
        try:
            await self._get_lektrico_device_settings_and_treat_unique_id(
                raise_on_progress=True
            )
        except DeviceConnectionError:
            return self._async_show_setup_form(
                {"base": "cannot_connect"}, {CONF_HOST: "cannot_connect"}
            )

        return self._async_create_entry()

    @callback
    def _async_show_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FRIENDLY_NAME,
                        default=user_input.get(CONF_FRIENDLY_NAME, ""),
                    ): str,
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                }
            ),
            errors=errors or {},
        )

    @callback
    def _async_create_entry(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title=f"{self._friendly_name} ({self._serial_number})",
            data={
                CONF_HOST: self._host,
                CONF_FRIENDLY_NAME: self._friendly_name,
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
        _id = discovery_info.properties.get("id")  # 1p7k_500006

        if _id is None:
            # properties have no "id"
            return self.async_abort(reason="missing_id")
        _index = _id.find("_")
        if _index == -1:
            # "id" does not contain "_"
            return self.async_abort(reason="missing_underline_in_id")
        self._serial_number = _id[_index + 1 :]
        if _id.startswith("m2w_81"):
            self._friendly_name = Device.TYPE_EM
        elif _id.startswith("m2w_83"):
            self._friendly_name = Device.TYPE_3EM
        else:
            self._friendly_name = _id[:_index]  # it's the type

        # read from device its settings
        try:
            await self._get_lektrico_device_settings_and_treat_unique_id(
                raise_on_progress=True
            )
        except DeviceConnectionError:
            return self._async_show_setup_form(
                {"base": "cannot_connect"}, {CONF_HOST: "cannot_connect"}
            )

        self.context["title_placeholders"] = {
            "serial_number": self._serial_number,
            "friendly_name": self._friendly_name,
        }

        return await self.async_step_confirm()

    async def _get_lektrico_device_settings_and_treat_unique_id(
        self, raise_on_progress: bool = True
    ) -> None:
        """Get device's serial number from a Lektrico device."""
        session = async_get_clientsession(self.hass)
        device = Device(
            _host=self._host,
            session=session,
        )

        _settings = await device.device_config()
        self._serial_number = str(_settings.serial_number)
        self._device_type = _settings.type
        self._board_revision = _settings.board_revision

        # Check if already configured
        # Set unique id
        await self.async_set_unique_id(
            self._serial_number, raise_on_progress=raise_on_progress
        )
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
