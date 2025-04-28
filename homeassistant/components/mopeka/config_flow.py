"""Config flow for mopeka integration."""

from __future__ import annotations

from enum import Enum
from typing import Any

from mopeka_iot_ble import MopekaIOTBluetoothDeviceData as DeviceData
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import CONF_MEDIUM_TYPE, DEFAULT_MEDIUM_TYPE, DOMAIN, MediumType


def format_medium_type(medium_type: Enum) -> str:
    """Format the medium type for human reading."""
    return medium_type.name.replace("_", " ").title()


MEDIUM_TYPES_BY_NAME = {
    medium.value: format_medium_type(medium) for medium in MediumType
}


def async_generate_schema(medium_type: str | None = None) -> vol.Schema:
    """Return the base schema with formatted medium types."""
    return vol.Schema(
        {
            vol.Required(
                CONF_MEDIUM_TYPE, default=medium_type or DEFAULT_MEDIUM_TYPE
            ): vol.In(MEDIUM_TYPES_BY_NAME)
        }
    )


class MopekaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for mopeka."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_device: DeviceData | None = None
        self._discovered_devices: dict[str, str] = {}

    @callback
    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MopekaOptionsFlow:
        """Return the options flow for this handler."""
        return MopekaOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = DeviceData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery and select medium type."""
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        title = device.title or device.get_device_name() or discovery_info.name
        if user_input is not None:
            self._discovered_devices[discovery_info.address] = title
            return self.async_create_entry(
                title=self._discovered_devices[discovery_info.address],
                data={CONF_MEDIUM_TYPE: user_input[CONF_MEDIUM_TYPE]},
            )

        self._set_confirm_only()
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
            data_schema=async_generate_schema(),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device and select medium type."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address],
                data={CONF_MEDIUM_TYPE: user_input[CONF_MEDIUM_TYPE]},
            )

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = DeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = (
                    device.title or device.get_device_name() or discovery_info.name
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices),
                    **async_generate_schema().schema,
                }
            ),
        )


class MopekaOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the Mopeka component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            new_data = {
                **self.config_entry.data,
                CONF_MEDIUM_TYPE: user_input[CONF_MEDIUM_TYPE],
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=async_generate_schema(
                self.config_entry.data.get(CONF_MEDIUM_TYPE)
            ),
        )
