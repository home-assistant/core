"""Config flow for Decora BLE."""
from __future__ import annotations

import logging
from typing import Any, Optional

from decora_bleak import DECORA_SERVICE_UUID, DecoraBLEDevice
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS, CONF_API_KEY, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class DecoraBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Decora BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None

        address = self._discovery_info.address

        errors: dict[str, str] = {}

        if user_input is not None:
            api_key, error = await self._get_api_key(address)
            if api_key is not None:
                assert error is None
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_ADDRESS: address.upper(), CONF_API_KEY: api_key},
                )

            if error is not None:
                errors["base"] = error

        placeholders = {"name": self._discovery_info.name}
        self.context["title_placeholders"] = placeholders

        field_values = user_input if user_input is not None else {}
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=field_values.get(CONF_NAME)): str,
            }
        )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            api_key, error = await self._get_api_key(address)
            if api_key is not None:
                assert error is None
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_ADDRESS: address.upper(), CONF_API_KEY: api_key},
                )

            if error is not None:
                errors["base"] = error

        current_addresses = self._async_current_ids()
        for discovery in async_discovered_service_info(self.hass):
            if (
                discovery.address in current_addresses
                or discovery.address in self._discovered_devices
                or DECORA_SERVICE_UUID not in discovery.service_uuids
            ):
                continue
            self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        field_values = user_input if user_input is not None else {}
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: (
                            f"{service_info.name} ({service_info.address})"
                        )
                        for service_info in self._discovered_devices.values()
                    }
                ),
                vol.Required(CONF_NAME, default=field_values.get(CONF_NAME)): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _get_api_key(self, address: str) -> tuple[Optional[str], Optional[str]]:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, address.upper(), connectable=True
        )

        if ble_device:
            api_key = await DecoraBLEDevice.get_api_key(ble_device)
            if api_key is not None:
                return api_key, None

            return None, "not_in_pairing_mode"

        return None, "cannot_connect"
