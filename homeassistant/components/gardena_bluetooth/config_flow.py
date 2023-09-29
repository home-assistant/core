"""Config flow for Gardena Bluetooth integration."""
from __future__ import annotations

import logging
from typing import Any

from gardena_bluetooth.client import Client
from gardena_bluetooth.const import DeviceInformation, ScanService
from gardena_bluetooth.exceptions import CharacteristicNotFound, CommunicationFailure
from gardena_bluetooth.parse import ManufacturerData, ProductGroup
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import AbortFlow, FlowResult

from . import get_connection
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _is_supported(discovery_info: BluetoothServiceInfo):
    """Check if device is supported."""
    if ScanService not in discovery_info.service_uuids:
        return False

    if not (data := discovery_info.manufacturer_data.get(ManufacturerData.company)):
        _LOGGER.debug("Missing manufacturer data: %s", discovery_info)
        return False

    manufacturer_data = ManufacturerData.decode(data)
    if manufacturer_data.group != ProductGroup.WATER_CONTROL:
        _LOGGER.debug("Unsupported device: %s", manufacturer_data)
        return False

    return True


def _get_name(discovery_info: BluetoothServiceInfo):
    if discovery_info.name and discovery_info.name != discovery_info.address:
        return discovery_info.name
    return "Gardena Device"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gardena Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.devices: dict[str, str] = {}
        self.address: str | None

    async def async_read_data(self):
        """Try to connect to device and extract information."""
        client = Client(get_connection(self.hass, self.address))
        try:
            model = await client.read_char(DeviceInformation.model_number)
            _LOGGER.debug("Found device with model: %s", model)
        except (CharacteristicNotFound, CommunicationFailure) as exception:
            raise AbortFlow(
                "cannot_connect", description_placeholders={"error": str(exception)}
            ) from exception
        finally:
            await client.disconnect()

        return {CONF_ADDRESS: self.address}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered device: %s", discovery_info)
        if not _is_supported(discovery_info):
            return self.async_abort(reason="no_devices_found")

        self.address = discovery_info.address
        self.devices = {discovery_info.address: _get_name(discovery_info)}
        await self.async_set_unique_id(self.address)
        self._abort_if_unique_id_configured()
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self.address
        title = self.devices[self.address]

        if user_input is not None:
            data = await self.async_read_data()
            return self.async_create_entry(title=title, data=data)

        self.context["title_placeholders"] = {
            "name": title,
        }

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self.address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(self.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_confirm()

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            if address in current_addresses or not _is_supported(discovery_info):
                continue

            self.devices[address] = _get_name(discovery_info)

        if not self.devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(self.devices),
                },
            ),
        )
