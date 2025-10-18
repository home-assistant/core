"""Config flow for the ToGrill integration."""

from __future__ import annotations

from typing import Any

from bleak.exc import BleakError
from togrill_bluetooth import SUPPORTED_DEVICES
from togrill_bluetooth.client import Client
from togrill_bluetooth.packets import PacketA0Notify
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow

from .const import CONF_PROBE_COUNT, DOMAIN
from .coordinator import LOGGER

_TIMEOUT = 10


async def read_config_data(
    hass: HomeAssistant, info: BluetoothServiceInfoBleak
) -> dict[str, Any]:
    """Read config from device."""

    try:
        client = await Client.connect(info.device)
    except BleakError as exc:
        LOGGER.debug("Failed to connect", exc_info=True)
        raise AbortFlow("failed_to_read_config") from exc

    try:
        packet_a0 = await client.read(PacketA0Notify)
    except BleakError as exc:
        LOGGER.debug("Failed to read data", exc_info=True)
        raise AbortFlow("failed_to_read_config") from exc
    finally:
        await client.disconnect()

    return {
        CONF_MODEL: info.name,
        CONF_ADDRESS: info.address,
        CONF_PROBE_COUNT: packet_a0.probe_count,
    }


class ToGrillBluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ToGrillBluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovery_infos: dict[str, BluetoothServiceInfoBleak] = {}

    async def _async_create_entry_internal(
        self, info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        config_data = await read_config_data(self.hass, info)

        return self.async_create_entry(
            title=config_data[CONF_MODEL],
            data=config_data,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        if discovery_info.name not in SUPPORTED_DEVICES:
            return self.async_abort(reason="not_supported")

        self._discovery_info = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info

        if user_input is not None:
            return await self._async_create_entry_internal(discovery_info)

        self._set_confirm_only()
        placeholders = {"name": discovery_info.name}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return await self._async_create_entry_internal(
                self._discovery_infos[address]
            )

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, True):
            address = discovery_info.address
            if (
                address in current_addresses
                or address in self._discovery_infos
                or discovery_info.name not in SUPPORTED_DEVICES
            ):
                continue
            self._discovery_infos[address] = discovery_info

        if not self._discovery_infos:
            return self.async_abort(reason="no_devices_found")

        addresses = {info.address: info.name for info in self._discovery_infos.values()}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(addresses)}),
        )
