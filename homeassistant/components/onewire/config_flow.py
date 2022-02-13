"""Config flow for 1-Wire component."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry

from .const import (
    CONF_MOUNT_DIR,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_OWSERVER_HOST,
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DEVICE_SUPPORT_PRECISION_MAPPING,
    DOMAIN,
    INPUT_ENTRY_CLEAR_OPTIONS,
    INPUT_ENTRY_DEVICE_SELECTION,
    OPTION_ENTRY_DEVICE_OPTIONS,
    OPTION_ENTRY_SENSOR_PRECISION,
    PRECISION_MAPPING_FAMILY_28,
)
from .model import OWServerDeviceDescription
from .onewirehub import CannotConnect, InvalidPath, OneWireHub

DATA_SCHEMA_USER = vol.Schema(
    {vol.Required(CONF_TYPE): vol.In([CONF_TYPE_OWSERVER, CONF_TYPE_SYSBUS])}
)
DATA_SCHEMA_OWSERVER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_OWSERVER_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_OWSERVER_PORT): int,
    }
)
DATA_SCHEMA_MOUNTDIR = vol.Schema(
    {
        vol.Required(CONF_MOUNT_DIR, default=DEFAULT_SYSBUS_MOUNT_DIR): str,
    }
)


_LOGGER = logging.getLogger(__name__)


async def validate_input_owserver(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA_OWSERVER with values provided by the user.
    """

    hub = OneWireHub(hass)

    host = data[CONF_HOST]
    port = data[CONF_PORT]
    # Raises CannotConnect exception on failure
    await hub.connect(host, port)

    # Return info that you want to store in the config entry.
    return {"title": host}


async def validate_input_mount_dir(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA_MOUNTDIR with values provided by the user.
    """
    hub = OneWireHub(hass)

    mount_dir = data[CONF_MOUNT_DIR]

    # Raises InvalidDir exception on failure
    await hub.check_mount_dir(mount_dir)

    # Return info that you want to store in the config entry.
    return {"title": mount_dir}


class OneWireFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle 1-Wire config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize 1-Wire config flow."""
        self.onewire_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle 1-Wire config flow start.

        Let user manually input configuration.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            self.onewire_config.update(user_input)
            if CONF_TYPE_OWSERVER == user_input[CONF_TYPE]:
                return await self.async_step_owserver()
            if CONF_TYPE_SYSBUS == user_input[CONF_TYPE]:
                return await self.async_step_mount_dir()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_USER,
            errors=errors,
        )

    async def async_step_owserver(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle OWServer configuration."""
        errors = {}
        if user_input:
            # Prevent duplicate entries
            self._async_abort_entries_match(
                {
                    CONF_TYPE: CONF_TYPE_OWSERVER,
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )

            self.onewire_config.update(user_input)

            try:
                info = await validate_input_owserver(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=info["title"], data=self.onewire_config
                )

        return self.async_show_form(
            step_id="owserver",
            data_schema=DATA_SCHEMA_OWSERVER,
            errors=errors,
        )

    async def async_step_mount_dir(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SysBus configuration."""
        errors = {}
        if user_input:
            # Prevent duplicate entries
            await self.async_set_unique_id(
                f"{CONF_TYPE_SYSBUS}:{user_input[CONF_MOUNT_DIR]}"
            )
            self._abort_if_unique_id_configured()

            self.onewire_config.update(user_input)

            try:
                info = await validate_input_mount_dir(self.hass, user_input)
            except InvalidPath:
                errors["base"] = "invalid_path"
            else:
                return self.async_create_entry(
                    title=info["title"], data=self.onewire_config
                )

        return self.async_show_form(
            step_id="mount_dir",
            data_schema=DATA_SCHEMA_MOUNTDIR,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OnewireOptionsFlowHandler(config_entry)


class OnewireOptionsFlowHandler(OptionsFlow):
    """Handle OneWire Config options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize OneWire Network options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.controller: OneWireHub
        self.device_registry: DeviceRegistry | None = None
        self.configurable_devices: list[str] = []
        self.configurable_devices_precision: list[str] = []
        self.devices_to_configure_total: list[str] = []
        self.devices_to_configure_precision: list[str] = []
        self.current_device: str = ""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        self.controller = self.hass.data[DOMAIN][self.config_entry.entry_id]
        if self.controller.type == CONF_TYPE_SYSBUS:
            return self.async_abort(
                reason="SysBus setup does not have any config options."
            )

        self.device_registry = dr.async_get(self.hass)
        if self.controller.devices:
            self.configurable_devices_precision = [
                device.id
                for device in self.controller.devices
                if isinstance(device, OWServerDeviceDescription)
                and device.family in DEVICE_SUPPORT_PRECISION_MAPPING
            ]
            # Join all lists of devicesin the future
            self.configurable_devices = self.configurable_devices_precision.copy()

        return await self.async_step_device_selection(user_input=None)

    async def async_step_device_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select what devices to configure."""

        if user_input is not None:
            if user_input.get(INPUT_ENTRY_CLEAR_OPTIONS):
                self.options = {}
            else:
                device_selection_list = (
                    user_input.get(INPUT_ENTRY_DEVICE_SELECTION) or []
                )
                self.devices_to_configure_total = [
                    device_id
                    for device_id in device_selection_list
                    if isinstance(device_id, str)
                ]
                self.devices_to_configure_precision = [
                    self._get_device_id_from_long_name(device_id)
                    for device_id in self.devices_to_configure_total
                    if self._get_device_id_from_long_name(device_id)
                    in self.configurable_devices_precision
                ]
                return await self.async_step_precision_config(user_input=None)
            return await self._update_options()

        return self.async_show_form(
            step_id="device_selection",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        INPUT_ENTRY_CLEAR_OPTIONS,
                        default=False,
                    ): bool,
                    vol.Optional(
                        INPUT_ENTRY_DEVICE_SELECTION,
                        default=self._get_current_configured_sensors(),
                        description="Multiselect with list of devices to choose from",
                    ): cv.multi_select(
                        {
                            device: False
                            for device in self._get_configurable_list_as_long_names()
                        }
                    ),
                }
            ),
        )

    async def async_step_precision_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Config precision option for device."""
        if user_input is not None or len(self.devices_to_configure_precision) <= 0:
            self._update_precision_config_option(self.current_device, user_input)
            if len(self.devices_to_configure_precision) > 0:
                return await self.async_step_precision_config(user_input=None)
            self.current_device = ""
            return await self._update_options()

        self.current_device = self.devices_to_configure_precision.pop()
        return self.async_show_form(
            step_id="precision_config",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPTION_ENTRY_SENSOR_PRECISION,
                        default=self._get_current_precision_setting(
                            self.current_device
                        ),
                    ): vol.In(list(PRECISION_MAPPING_FAMILY_28.keys())),
                }
            ),
            description_placeholders={
                "sens_id": self._get_device_long_name_from_id(self.current_device)
            },
        )

    async def _update_options(self) -> FlowResult:
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)

    def _get_device_long_name_from_id(self, current_device: str) -> str:
        device: DeviceEntry | None
        assert self.device_registry
        device = self.device_registry.async_get_device({(DOMAIN, current_device)})
        if device and device.name_by_user:
            return f"{device.name_by_user} ({current_device})"
        return current_device

    @staticmethod
    def _get_device_id_from_long_name(device_name: str) -> str:
        if "(" in device_name:
            return device_name.split("(")[1].replace(")", "")
        return device_name

    def _get_configurable_list_as_long_names(self) -> list[str]:
        return [
            self._get_device_long_name_from_id(device_id)
            for device_id in self.configurable_devices
        ]

    def _get_current_configured_sensors(self) -> list[str] | None:
        """Get current list of sensors that are configured."""
        configured_sensors = self.options.get(OPTION_ENTRY_DEVICE_OPTIONS)
        if configured_sensors is None:
            return []
        return [
            self._get_device_long_name_from_id(device_id)
            for device_id in self.configurable_devices
            if device_id in configured_sensors
        ]

    def _get_current_precision_setting(self, device: str) -> str:
        """Get current value for precision setting."""
        return_string = "Default"
        try:
            precision_setting = self.options[OPTION_ENTRY_DEVICE_OPTIONS][device][
                OPTION_ENTRY_SENSOR_PRECISION
            ]
            if isinstance(precision_setting, str):
                return_string = precision_setting
        except KeyError:
            pass
        return return_string

    def _update_precision_config_option(
        self, device: str, user_input: dict[str, Any] | None
    ) -> None:
        """Update the device config with the new precision for the actual device."""
        if not device or not user_input:
            return
        if OPTION_ENTRY_DEVICE_OPTIONS not in self.options:
            self.options[OPTION_ENTRY_DEVICE_OPTIONS] = {}
        sensor_options_entry = self.options[OPTION_ENTRY_DEVICE_OPTIONS]
        if device not in sensor_options_entry:
            sensor_options_entry[device] = {}
        sensor_options_entry[device][OPTION_ENTRY_SENSOR_PRECISION] = user_input[
            OPTION_ENTRY_SENSOR_PRECISION
        ]
        self.options.update({OPTION_ENTRY_DEVICE_OPTIONS: sensor_options_entry})
