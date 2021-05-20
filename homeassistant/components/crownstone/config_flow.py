"""Flow handler for Crownstone."""
from __future__ import annotations

from typing import Any, Final, cast

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD, CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import CONF_USB, CONF_USB_PATH, CONF_USE_CROWNSTONE_USB
from .const import DOMAIN  # pylint: disable=unused-import
from .helpers import get_serial_by_id

REFRESH_LIST: Final = "Refresh list"


class CrownstoneConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crownstone."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CrownstoneOptionsFlowHandler:
        """Return the Crownstone options."""
        return CrownstoneOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the flow."""
        self.cloud = cast(CrownstoneCloud, None)
        self.login_info = cast(dict[str, Any], None)
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

        self.cloud = CrownstoneCloud(
            email=user_input[CONF_EMAIL],
            password=user_input[CONF_PASSWORD],
            clientsession=aiohttp_client.async_get_clientsession(self.hass),
        )

        try:
            # get all cloud data for this account
            await self.cloud.async_initialize()

            # set unique id and abort if already configured
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            # start next flow
            self.login_info = user_input
            return await self.async_step_usb()
        except CrownstoneAuthenticationError as auth_error:
            if auth_error.type == "LOGIN_FAILED":
                errors["base"] = "invalid_auth"
            if auth_error.type == "LOGIN_FAILED_EMAIL_NOT_VERIFIED":
                errors["base"] = "account_not_verified"
        except CrownstoneUnknownError:
            errors["base"] = "unknown_error"

        # show form again, with the error
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_usb(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select whether a Crownstone USB should be used."""
        if user_input is None:
            return self.async_show_form(
                step_id="usb",
                data_schema=vol.Schema({vol.Optional(CONF_USB, default=False): bool}),
            )

        if user_input[CONF_USB]:
            return await self.async_step_usb_config()

        return self.async_return_entry()

    async def async_step_usb_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up a Crownstone USB Dongle."""
        # save outside of function in case of refresh
        list_of_ports = await self.hass.async_add_executor_job(
            serial.tools.list_ports.comports
        )
        ports_as_string = [
            f"{p}" + f" - {p.manufacturer}" if p.manufacturer else ""
            for p in list_of_ports
        ]
        ports_as_string.append(REFRESH_LIST)

        if user_input is not None:
            if user_input.get(CONF_UNIQUE_ID) is not None:
                # provided unique id from entry that needs to be updated
                self.existing_entry_id = user_input.get(CONF_UNIQUE_ID)

            if user_input.get(CONF_USB_PATH) is not None:
                selection = user_input[CONF_USB_PATH]
                # user can refresh the list while in this step
                if selection != REFRESH_LIST:
                    # get serial-id info
                    port: ListPortInfo = list_of_ports[ports_as_string.index(selection)]
                    self.usb_path = await self.hass.async_add_executor_job(
                        get_serial_by_id, port.device
                    )

                    # check if we are updating an existing entry
                    if self.existing_entry_id is not None:
                        existing_entry = self.hass.config_entries.async_get_entry(
                            self.existing_entry_id
                        )
                        if existing_entry is not None:
                            # copy instead of directly changing memory
                            data = existing_entry.data.copy()
                            data[CONF_USB_PATH] = self.usb_path
                            # update entry & reload
                            self.hass.config_entries.async_update_entry(
                                existing_entry, data=data
                            )
                            await self.hass.config_entries.async_reload(
                                existing_entry.entry_id
                            )
                            # this exits the flow immediately
                            return self.async_abort(reason="usb_setup_successful")

                        # if we couldn't find the entry, which is unlikely
                        return self.async_abort(reason="usb_setup_unsuccessful")

                    return self.async_return_entry()

        return self.async_show_form(
            step_id="usb_config",
            data_schema=vol.Schema(
                {vol.Required(CONF_USB_PATH): vol.In(ports_as_string)}
            ),
        )

    def async_return_entry(self) -> FlowResult:
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
