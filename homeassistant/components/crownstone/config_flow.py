"""Flow handler for Crownstone."""
from __future__ import annotations

from typing import Any

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD, CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_USB_MANUAL_PATH,
    CONF_USB_PATH,
    CONF_USE_CROWNSTONE_USB,
    DOMAIN,
    DONT_USE_USB,
    MANUAL_PATH,
    REFRESH_LIST,
)
from .helpers import get_serial_by_id


class CrownstoneConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crownstone."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CrownstoneOptionsFlowHandler:
        """Return the Crownstone options."""
        return CrownstoneOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the flow."""
        self.login_info: dict[str, Any] = {}
        self.usb_path: str | None = None
        self.existing_entry_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
                ),
            )

        cloud = CrownstoneCloud(
            email=user_input[CONF_EMAIL],
            password=user_input[CONF_PASSWORD],
            clientsession=aiohttp_client.async_get_clientsession(self.hass),
        )

        try:
            # get all cloud data for this account
            await cloud.async_initialize()
        except CrownstoneAuthenticationError as auth_error:
            if auth_error.type == "LOGIN_FAILED":
                errors["base"] = "invalid_auth"
            elif auth_error.type == "LOGIN_FAILED_EMAIL_NOT_VERIFIED":
                errors["base"] = "account_not_verified"
        except CrownstoneUnknownError:
            errors["base"] = "unknown_error"

        # show form again, with the errors
        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
                ),
                errors=errors,
            )

        # set unique id and abort if already configured
        await self.async_set_unique_id(user_input[CONF_EMAIL])
        self._abort_if_unique_id_configured()

        # start next flow
        self.login_info = user_input
        return await self.async_step_usb_config()

    async def async_step_usb_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up a Crownstone USB dongle."""
        list_of_ports = await self.hass.async_add_executor_job(
            serial.tools.list_ports.comports
        )
        ports_as_string = [DONT_USE_USB]
        for port in list_of_ports:
            ports_as_string.append(
                f"{port.device}"
                + f" - {port.product}"
                + f" - {format(port.vid, 'x')}:{format(port.pid, 'x')}"
            )
        ports_as_string.append(MANUAL_PATH)
        ports_as_string.append(REFRESH_LIST)

        if user_input is not None:
            if user_input.get(CONF_UNIQUE_ID) is not None:
                # provided unique id from entry that needs to be updated
                self.existing_entry_id = user_input.get(CONF_UNIQUE_ID)

            if user_input.get(CONF_USB_PATH) is not None:
                selection = user_input[CONF_USB_PATH]

                # no usb should be used, finish flow
                if selection == DONT_USE_USB:
                    return self.async_finish_flow()

                # show a form with text field to enter manual path
                if selection == MANUAL_PATH:
                    return await self.async_step_usb_manual_config()

                # user can refresh the list while in this step
                if selection != REFRESH_LIST:
                    # get serial-id info
                    selected_port: ListPortInfo = list_of_ports[
                        (ports_as_string.index(selection) - 1)
                    ]
                    self.usb_path = await self.hass.async_add_executor_job(
                        get_serial_by_id, selected_port.device
                    )

                    # check if we are updating an existing entry
                    if self.existing_entry_id is not None:
                        return await self.async_update_existing_entry_usb_path()

                    return self.async_finish_flow()

        return self.async_show_form(
            step_id="usb_config",
            data_schema=vol.Schema(
                {vol.Required(CONF_USB_PATH): vol.In(ports_as_string)}
            ),
        )

    async def async_step_usb_manual_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manually enter Crownstone USB dongle path."""
        if user_input is None:
            return self.async_show_form(
                step_id="usb_manual_config",
                data_schema=vol.Schema({vol.Required(CONF_USB_MANUAL_PATH): str}),
            )

        # save usb path
        self.usb_path = user_input[CONF_USB_MANUAL_PATH]

        # check if we are updating an existing entry
        if self.existing_entry_id is not None:
            return await self.async_update_existing_entry_usb_path()

        return self.async_finish_flow()

    async def async_update_existing_entry_usb_path(self) -> FlowResult:
        """Update usb path of existing entry."""
        existing_entry = self.hass.config_entries.async_get_entry(
            str(self.existing_entry_id)
        )
        if existing_entry is not None:
            # copy instead of directly changing memory
            data = existing_entry.data.copy()
            data[CONF_USB_PATH] = self.usb_path
            # update entry & reload
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            # this exits the flow immediately
            return self.async_abort(reason="usb_setup_complete")

        # if we couldn't find the entry
        return self.async_abort(reason="usb_setup_unsuccessful")

    def async_finish_flow(self) -> FlowResult:
        """Create a new entry."""
        return self.async_create_entry(
            title=f"Account: {self.unique_id}",
            data={
                CONF_ID: self.unique_id,
                CONF_EMAIL: self.login_info[CONF_EMAIL],
                CONF_PASSWORD: self.login_info[CONF_PASSWORD],
                CONF_USB_PATH: self.usb_path,
            },
        )


class CrownstoneOptionsFlowHandler(OptionsFlow):
    """Handle Crownstone options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Crownstone options."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Crownstone options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_USE_CROWNSTONE_USB,
                        default=self.config_entry.data.get(CONF_USB_PATH) is not None,
                    ): bool
                }
            ),
        )
