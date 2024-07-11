"""Config flow for 1-Wire component."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEVICE_SUPPORT_OPTIONS,
    DOMAIN,
    INPUT_ENTRY_CLEAR_OPTIONS,
    INPUT_ENTRY_DEVICE_SELECTION,
    OPTION_ENTRY_DEVICE_OPTIONS,
    OPTION_ENTRY_SENSOR_PRECISION,
    PRECISION_MAPPING_FAMILY_28,
)
from .onewirehub import CannotConnect, OneWireHub

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    hub = OneWireHub(hass)

    host = data[CONF_HOST]
    port = data[CONF_PORT]
    # Raises CannotConnect exception on failure
    await hub.connect(host, port)

    # Return info that you want to store in the config entry.
    return {"title": host}


class OneWireFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle 1-Wire config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize 1-Wire config flow."""
        self.onewire_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle 1-Wire config flow start.

        Let user manually input configuration.
        """
        errors: dict[str, str] = {}
        if user_input:
            # Prevent duplicate entries
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )

            self.onewire_config.update(user_input)

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=info["title"], data=self.onewire_config
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OnewireOptionsFlowHandler:
        """Get the options flow for this handler."""
        return OnewireOptionsFlowHandler(config_entry)


class OnewireOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle OneWire Config options."""

    configurable_devices: dict[str, str]
    """Mapping of the configurable devices.

        `key`: friendly name
        `value`: onewire id
    """
    devices_to_configure: dict[str, str]
    """Mapping of the devices selected for configuration.

        `key`: friendly name
        `value`: onewire id
    """
    current_device: str
    """Friendly name of the currently selected device."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        device_registry = dr.async_get(self.hass)
        self.configurable_devices = {
            self._get_device_friendly_name(device, device.name): device.name
            for device in dr.async_entries_for_config_entry(
                device_registry, self.config_entry.entry_id
            )
            if device.name and device.name[0:2] in DEVICE_SUPPORT_OPTIONS
        }

        if not self.configurable_devices:
            return self.async_abort(reason="No configurable devices found.")

        return await self.async_step_device_selection(user_input=None)

    async def async_step_device_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select what devices to configure."""
        errors = {}
        if user_input is not None:
            if user_input.get(INPUT_ENTRY_CLEAR_OPTIONS):
                # Reset all options
                return self.async_create_entry(data={})

            selected_devices: list[str] = (
                user_input.get(INPUT_ENTRY_DEVICE_SELECTION) or []
            )
            if selected_devices:
                self.devices_to_configure = {
                    friendly_name: self.configurable_devices[friendly_name]
                    for friendly_name in selected_devices
                }

                return await self.async_step_configure_device(user_input=None)
            errors["base"] = "device_not_selected"

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
                            friendly_name: False
                            for friendly_name in self.configurable_devices
                        }
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_configure_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Config precision option for device."""
        if user_input is not None:
            self._update_device_options(user_input)
            if self.devices_to_configure:
                return await self.async_step_configure_device(user_input=None)
            return self.async_create_entry(data=self.options)

        self.current_device, onewire_id = self.devices_to_configure.popitem()
        data_schema = vol.Schema(
            {
                vol.Required(
                    OPTION_ENTRY_SENSOR_PRECISION,
                    default=self._get_current_setting(
                        onewire_id, OPTION_ENTRY_SENSOR_PRECISION, "temperature"
                    ),
                ): vol.In(PRECISION_MAPPING_FAMILY_28),
            }
        )

        return self.async_show_form(
            step_id="configure_device",
            data_schema=data_schema,
            description_placeholders={"sensor_id": self.current_device},
        )

    @staticmethod
    def _get_device_friendly_name(entry: DeviceEntry, onewire_id: str) -> str:
        if entry.name_by_user:
            return f"{entry.name_by_user} ({onewire_id})"
        return onewire_id

    def _get_current_configured_sensors(self) -> list[str]:
        """Get current list of sensors that are configured."""
        configured_sensors = self.options.get(OPTION_ENTRY_DEVICE_OPTIONS)
        if not configured_sensors:
            return []
        return [
            friendly_name
            for friendly_name, onewire_id in self.configurable_devices.items()
            if onewire_id in configured_sensors
        ]

    def _get_current_setting(self, device_id: str, setting: str, default: Any) -> Any:
        """Get current value for setting."""
        if entry_device_options := self.options.get(OPTION_ENTRY_DEVICE_OPTIONS):
            if device_options := entry_device_options.get(device_id):
                return device_options.get(setting)
        return default

    def _update_device_options(self, user_input: dict[str, Any]) -> None:
        """Update the global config with the new options for the current device."""
        options: dict[str, dict[str, Any]] = self.options.setdefault(
            OPTION_ENTRY_DEVICE_OPTIONS, {}
        )

        onewire_id = self.configurable_devices[self.current_device]
        device_options: dict[str, Any] = options.setdefault(onewire_id, {})
        if onewire_id[0:2] == "28":
            device_options[OPTION_ENTRY_SENSOR_PRECISION] = user_input[
                OPTION_ENTRY_SENSOR_PRECISION
            ]

        self.options.update({OPTION_ENTRY_DEVICE_OPTIONS: options})
