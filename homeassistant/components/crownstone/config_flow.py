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

from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
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
from .entry_manager import CrownstoneEntryManager
from .helpers import list_ports_as_str


class CrownstoneConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crownstone."""

    VERSION = 1
    cloud: CrownstoneCloud

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
        self.usb_sphere_id: str | None = None

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

    async def async_step_usb_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up a Crownstone USB dongle."""
        list_of_ports = await self.hass.async_add_executor_job(
            serial.tools.list_ports.comports
        )
        ports_as_string = list_ports_as_str(list_of_ports)

        if user_input is not None:
            selection = user_input[CONF_USB_PATH]

            if selection == DONT_USE_USB:
                return self.async_create_new_entry()
            if selection == MANUAL_PATH:
                return await self.async_step_usb_manual_config()
            if selection != REFRESH_LIST:
                selected_port: ListPortInfo = list_of_ports[
                    (ports_as_string.index(selection) - 1)
                ]
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
    ) -> FlowResult:
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
    ) -> FlowResult:
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

        return self.async_create_new_entry()

    def async_create_new_entry(self) -> FlowResult:
        """Create a new entry."""
        return self.async_create_entry(
            title=f"Account: {self.login_info[CONF_EMAIL]}",
            data={
                CONF_EMAIL: self.login_info[CONF_EMAIL],
                CONF_PASSWORD: self.login_info[CONF_PASSWORD],
            },
            options={CONF_USB_PATH: self.usb_path, CONF_USB_SPHERE: self.usb_sphere_id},
        )


class CrownstoneOptionsFlowHandler(OptionsFlow):
    """Handle Crownstone options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Crownstone options."""
        self.entry = config_entry
        self.updated_options = config_entry.options.copy()
        self.spheres: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Crownstone options."""
        manager: CrownstoneEntryManager = self.hass.data[DOMAIN][self.entry.entry_id]

        spheres = {sphere.name: sphere.cloud_id for sphere in manager.cloud.cloud_data}
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
                        default=manager.cloud.cloud_data.spheres[usb_sphere].name,
                    ): vol.In(spheres.keys())
                }
            )

        if user_input is not None:
            if user_input[CONF_USE_USB_OPTION] and usb_path is None:
                self.spheres = spheres
                return await self.async_step_usb_config_option()
            if not user_input[CONF_USE_USB_OPTION] and usb_path is not None:
                self.updated_options[CONF_USB_PATH] = None
                self.updated_options[CONF_USB_SPHERE] = None
            elif (
                CONF_USB_SPHERE_OPTION in user_input
                and spheres[user_input[CONF_USB_SPHERE_OPTION]] != usb_sphere
            ):
                sphere_id = spheres[user_input[CONF_USB_SPHERE_OPTION]]
                user_input[CONF_USB_SPHERE_OPTION] = sphere_id
                self.updated_options[CONF_USB_SPHERE] = sphere_id

            return self.async_create_entry(title="", data=self.updated_options)

        return self.async_show_form(step_id="init", data_schema=options_schema)

    async def async_step_usb_config_option(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up a Crownstone USB dongle."""
        list_of_ports = await self.hass.async_add_executor_job(
            serial.tools.list_ports.comports
        )
        ports_as_string = list_ports_as_str(list_of_ports, False)

        if user_input is not None:
            selection = user_input[CONF_USB_PATH]

            if selection == MANUAL_PATH:
                return await self.async_step_usb_manual_config_option()
            if selection != REFRESH_LIST:
                selected_port: ListPortInfo = list_of_ports[
                    ports_as_string.index(selection)
                ]
                usb_path = await self.hass.async_add_executor_job(
                    usb.get_serial_by_id, selected_port.device
                )
                self.updated_options[CONF_USB_PATH] = usb_path
                return await self.async_step_usb_sphere_config_option()

        return self.async_show_form(
            step_id="usb_config_option",
            data_schema=vol.Schema(
                {vol.Required(CONF_USB_PATH): vol.In(ports_as_string)}
            ),
        )

    async def async_step_usb_manual_config_option(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manually enter Crownstone USB dongle path."""
        if user_input is None:
            return self.async_show_form(
                step_id="usb_manual_config_option",
                data_schema=vol.Schema({vol.Required(CONF_USB_MANUAL_PATH): str}),
            )

        self.updated_options[CONF_USB_PATH] = user_input[CONF_USB_MANUAL_PATH]
        return await self.async_step_usb_sphere_config_option()

    async def async_step_usb_sphere_config_option(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a Crownstone sphere that the USB operates in."""
        # no need to select if there's only 1 option
        sphere_id: str | None = None
        if len(self.spheres) == 1:
            sphere_id = next(iter(self.spheres.values()))

        if user_input is None and sphere_id is None:
            return self.async_show_form(
                step_id="usb_sphere_config_option",
                data_schema=vol.Schema({CONF_USB_SPHERE: vol.In(self.spheres.keys())}),
            )

        if sphere_id:
            self.updated_options[CONF_USB_SPHERE] = sphere_id
        elif user_input:
            self.updated_options[CONF_USB_SPHERE] = self.spheres[
                user_input[CONF_USB_SPHERE]
            ]

        return self.async_create_entry(title="", data=self.updated_options)
