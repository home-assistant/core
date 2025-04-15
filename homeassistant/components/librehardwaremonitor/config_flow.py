"""Config flow for LibreHardwareMonitor."""

from __future__ import annotations

import logging
from typing import Any

from librehardwaremonitor_api import (
    LibreHardwareMonitorClient,
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import selector

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_CONFIG_VALUES = {
    CONF_HOST: DEFAULT_HOST,
    CONF_PORT: DEFAULT_PORT,
}


class LibreHardwareMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LibreHardwareMonitor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._lhm_config_data: dict[str, Any] = {}
        self._main_devices: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        defaults = DEFAULT_CONFIG_VALUES
        if self.source == SOURCE_RECONFIGURE:
            defaults = dict(self._get_reconfigure_entry().data)

        config_data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=defaults[CONF_PORT]): int,
            }
        )
        errors = {}

        if user_input is not None:
            self._lhm_config_data = user_input

            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            if self.source == SOURCE_USER:
                self._abort_if_unique_id_configured()

            api = LibreHardwareMonitorClient(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )

            try:
                self._main_devices = await api.get_main_hardware_devices()
            except LibreHardwareMonitorConnectionError:
                _LOGGER.debug(
                    "ConnectionError: Is LibreHardwareMonitor running and the web server option enabled?"
                )
                errors["base"] = "cannot_connect"
            except LibreHardwareMonitorNoDevicesError:
                _LOGGER.debug(
                    "NoDevicesError: LibreHardwareMonitor did not return any devices"
                )
                errors["base"] = "no_devices"
            else:
                return await self.async_step_select_devices()

        return self.async_show_form(
            step_id="user", data_schema=config_data_schema, errors=errors
        )

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device selection step."""
        default_devices = self._main_devices
        if self.source == SOURCE_RECONFIGURE:
            configured_devices = self._get_reconfigure_entry().options[CONF_DEVICES]
            default_devices = [
                device for device in configured_devices if device in default_devices
            ]

        devices_data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICES, default=default_devices): selector(
                    {
                        "select": {
                            "options": self._main_devices,
                            "multiple": True,
                            "mode": "list",
                        }
                    }
                )
            }
        )

        if user_input is not None:
            if all(not value for value in user_input.values()):
                return self.async_show_form(
                    step_id="select_devices",
                    data_schema=devices_data_schema,
                    errors={"base": "no_devices_selected"},
                )

            selected_devices = user_input[CONF_DEVICES]
            _LOGGER.debug("Selected devices: %s", selected_devices)

            if self.source == SOURCE_RECONFIGURE:
                self._abort_if_unique_id_mismatch()
                await self._async_delete_orphaned_devices(selected_devices)
                return self.async_update_reload_and_abort(
                    entry=self._get_reconfigure_entry(),
                    data=self._lhm_config_data,
                    options={CONF_DEVICES: selected_devices},
                )

            return self.async_create_entry(
                title=f"{self._lhm_config_data[CONF_HOST]}:{self._lhm_config_data[CONF_PORT]}",
                data=self._lhm_config_data,
                options={CONF_DEVICES: selected_devices},
            )

        return self.async_show_form(
            step_id="select_devices", data_schema=devices_data_schema
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()

    async def _async_delete_orphaned_devices(self, selected_devices):
        """Delete any previously active devices that are no longer selected after reconfiguration."""
        previous_devices = self._get_reconfigure_entry().options[CONF_DEVICES]
        orphaned_devices = list(set(previous_devices) - set(selected_devices))
        for device_name in orphaned_devices:
            device_identifiers = {(DOMAIN, device_name)}
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_or_create(
                config_entry_id=self._reconfigure_entry_id,
                identifiers=device_identifiers,
            )
            device_registry.async_remove_device(device.id)
            _LOGGER.debug("Device %s (%s) removed", device.name, device.id)
