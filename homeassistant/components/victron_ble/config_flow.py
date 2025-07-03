"""Config flow for Victron Bluetooth Low Energy integration."""

from __future__ import annotations

import logging
from typing import Any

from victron_ble_ha_parser import VictronBluetoothDeviceData
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_ACCESS_TOKEN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
    }
)


class VictronBLEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron Bluetooth Low Energy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: str | None = None
        self._discovered_devices: dict[str, str] = {}
        self._discovered_devices_info: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> config_entries.ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("async_step_bluetooth: %s", discovery_info.address)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = VictronBluetoothDeviceData()
        if not device.supported(discovery_info):
            _LOGGER.debug("device %s not supported", discovery_info.address)
            return self.async_abort(reason="not_supported")

        self._discovered_device = discovery_info.address
        self._discovered_devices_info[discovery_info.address] = discovery_info
        self._discovered_devices[discovery_info.address] = discovery_info.name

        self.context["title_placeholders"] = {"title": discovery_info.name}

        return await self.async_step_access_token()

    async def async_step_access_token(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle advertisement key input."""
        # should only be called if there are discovered devices
        assert self._discovered_device is not None
        assert self._discovered_devices_info is not None
        discovery_info = self._discovered_devices_info[self._discovered_device]
        assert discovery_info is not None
        title = discovery_info.name

        if user_input is not None:
            # see if we can create a device with the access token
            device = VictronBluetoothDeviceData(user_input[CONF_ACCESS_TOKEN])
            if device.validate_advertisement_key(
                discovery_info.manufacturer_data[VICTRON_IDENTIFIER]
            ):
                return self.async_create_entry(
                    title=title,
                    data=user_input,
                )
            return self.async_abort(reason="invalid_access_token")

        return self.async_show_form(
            step_id="access_token",
            data_schema=STEP_ACCESS_TOKEN_DATA_SCHEMA,
            description_placeholders={"title": title},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle select a device to set up."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovered_device = address
            title = self._discovered_devices_info[address].name
            return self.async_show_form(
                step_id="access_token",
                data_schema=STEP_ACCESS_TOKEN_DATA_SCHEMA,
                description_placeholders={"title": title},
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = VictronBluetoothDeviceData()
            if device.supported(discovery_info):
                self._discovered_devices_info[address] = discovery_info
                self._discovered_devices[address] = discovery_info.name

        if len(self._discovered_devices) < 1:
            return self.async_abort(reason="no_devices_found")

        _LOGGER.debug("Discovered %s devices", len(self._discovered_devices))

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )
