"""Flow handler for Crownstone."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo
import voluptuous as vol

from homeassistant.components import usb
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryBaseFlow,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_USB_MANUAL_PATH,
    CONF_USB_PATH,
    CONF_USB_SPHERE,
    CONF_USB_SPHERE_OPTION,
    CONF_USE_USB_OPTION,
    DOMAIN,
    DONT_USE_USB,
    MANUAL_PATH,
    REFRESH_LIST,
)
from .helpers import list_ports_as_str

CONFIG_FLOW = "config_flow"
OPTIONS_FLOW = "options_flow"


class BaseCrownstoneFlowHandler(ConfigEntryBaseFlow):
    """Represent the base flow for Crownstone."""

    cloud: CrownstoneCloud

    def __init__(
        self, flow_type: str, create_entry_cb: Callable[..., ConfigFlowResult]
    ) -> None:
        """Set up flow instance."""
        self.flow_type = flow_type
        self.create_entry_callback = create_entry_cb
        self.usb_path: str | None = None
        self.usb_sphere_id: str | None = None

    async def async_step_usb_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a Crownstone USB dongle."""
        list_of_ports = await self.hass.async_add_executor_job(
            serial.tools.list_ports.comports
        )
        if self.flow_type == CONFIG_FLOW:
            ports_as_string = list_ports_as_str(list_of_ports)
        else:
            ports_as_string = list_ports_as_str(list_of_ports, False)

        if user_input is not None:
            selection = user_input[CONF_USB_PATH]

            if selection == DONT_USE_USB:
                return self.create_entry_callback()
            if selection == MANUAL_PATH:
                return await self.async_step_usb_manual_config()
            if selection != REFRESH_LIST:
                if self.flow_type == OPTIONS_FLOW:
                    index = ports_as_string.index(selection)
                else:
                    index = ports_as_string.index(selection) - 1

                selected_port: ListPortInfo = list_of_ports[index]
                self.usb_path = await self.hass.async_add_executor_job(
                    usb.get_serial_by_id, selected_port.device
                )
                return await self.async_step_usb_sphere_config()

        return self.async_show_form(
            step_id="usb_config",
            data_schema=vol.Schema(
                {vol.Required(CONF_USB_PATH): vol.In(ports_as_string)}
            ),
        )

    async def async_step_usb_manual_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manually enter Crownstone USB dongle path."""
        if user_input is None:
            return self.async_show_form(
                step_id="usb_manual_config",
                data_schema=vol.Schema({vol.Required(CONF_USB_MANUAL_PATH): str}),
            )

        self.usb_path = user_input[CONF_USB_MANUAL_PATH]
        return await self.async_step_usb_sphere_config()

    async def async_step_usb_sphere_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a Crownstone sphere that the USB operates in."""
        spheres = {sphere.name: sphere.cloud_id for sphere in self.cloud.cloud_data}
        # no need to select if there's only 1 option
        sphere_id: str | None = None
        if len(spheres) == 1:
            sphere_id = next(iter(spheres.values()))

        if user_input is None and sphere_id is None:
            return self.async_show_form(
                step_id="usb_sphere_config",
                data_schema=vol.Schema({CONF_USB_SPHERE: vol.In(spheres.keys())}),
            )

        if sphere_id:
            self.usb_sphere_id = sphere_id
        elif user_input:
            self.usb_sphere_id = spheres[user_input[CONF_USB_SPHERE]]

        return self.create_entry_callback()


class CrownstoneConfigFlowHandler(BaseCrownstoneFlowHandler, ConfigFlow, domain=DOMAIN):
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
        super().__init__(CONFIG_FLOW, self.async_create_new_entry)
        self.login_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        # Login & sync all user data
        try:
            await self.cloud.async_initialize()
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

        await self.async_set_unique_id(self.cloud.cloud_data.user_id)
        self._abort_if_unique_id_configured()

        self.login_info = user_input
        return await self.async_step_usb_config()

    def async_create_new_entry(self) -> ConfigFlowResult:
        """Create a new entry."""
        return super().async_create_entry(
            title=f"Account: {self.login_info[CONF_EMAIL]}",
            data={
                CONF_EMAIL: self.login_info[CONF_EMAIL],
                CONF_PASSWORD: self.login_info[CONF_PASSWORD],
            },
            options={CONF_USB_PATH: self.usb_path, CONF_USB_SPHERE: self.usb_sphere_id},
        )


class CrownstoneOptionsFlowHandler(BaseCrownstoneFlowHandler, OptionsFlow):
    """Handle Crownstone options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Crownstone options."""
        super().__init__(OPTIONS_FLOW, self.async_create_new_entry)
        self.entry = config_entry
        self.updated_options = config_entry.options.copy()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Crownstone options."""
        self.cloud: CrownstoneCloud = self.hass.data[DOMAIN][self.entry.entry_id].cloud

        spheres = {sphere.name: sphere.cloud_id for sphere in self.cloud.cloud_data}
        usb_path = self.entry.options.get(CONF_USB_PATH)
        usb_sphere = self.entry.options.get(CONF_USB_SPHERE)

        options_schema = vol.Schema(
            {vol.Optional(CONF_USE_USB_OPTION, default=usb_path is not None): bool}
        )
        if usb_path is not None and len(spheres) > 1:
            options_schema = options_schema.extend(
                {
                    vol.Optional(
                        CONF_USB_SPHERE_OPTION,
                        default=self.cloud.cloud_data.data[usb_sphere].name,
                    ): vol.In(spheres.keys())
                }
            )

        if user_input is not None:
            if user_input[CONF_USE_USB_OPTION] and usb_path is None:
                return await self.async_step_usb_config()
            if not user_input[CONF_USE_USB_OPTION] and usb_path is not None:
                self.updated_options[CONF_USB_PATH] = None
                self.updated_options[CONF_USB_SPHERE] = None
            elif (
                CONF_USB_SPHERE_OPTION in user_input
                and spheres[user_input[CONF_USB_SPHERE_OPTION]] != usb_sphere
            ):
                sphere_id = spheres[user_input[CONF_USB_SPHERE_OPTION]]
                self.updated_options[CONF_USB_SPHERE] = sphere_id

            return self.async_create_new_entry()

        return self.async_show_form(step_id="init", data_schema=options_schema)

    def async_create_new_entry(self) -> ConfigFlowResult:
        """Create a new entry."""
        # these attributes will only change when a usb was configured
        if self.usb_path is not None and self.usb_sphere_id is not None:
            self.updated_options[CONF_USB_PATH] = self.usb_path
            self.updated_options[CONF_USB_SPHERE] = self.usb_sphere_id

        return super().async_create_entry(title="", data=self.updated_options)
