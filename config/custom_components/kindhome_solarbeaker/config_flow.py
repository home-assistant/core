from typing import Any

from .kindhome_solarbeaker_ble import KindhomeBluetoothDeviceData
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)

from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)


def log(f, m):
    _LOGGER.info(f"MATI {f}: {m}")


class KindhomeSolarbeakerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for kindhome."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        log("KindhomeSolarbeakerConfigFlow.__init__", "called!")
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_device: KindhomeBluetoothDeviceData | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
            self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        log("async_step_bluetooth", f"called! {discovery_info.as_dict()}")
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        log("async_step_bluetooth", f"address: {discovery_info.address} hasn't been configured")
        device = KindhomeBluetoothDeviceData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        log("async_step_bluetooth_confirm", "called!")
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None
        discovery_info = self._discovery_info

        log("async_step_bluetooth_confirm", "initial assertion passed")
        title = device.get_device_name() or discovery_info.name

        log("async_step_bluetooth_confirm",
            f"title = {title}, device.get_device_name() = {device.get_device_name()}, discovery_info.name = {discovery_info.name}")
        # TODO Mati: what does it do?
        # if user_input is not None:
        #     return self.async_create_entry(title=title, data={})

        self._set_confirm_only()
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""

        log("async_step_user", f"called!, user_input={user_input}")

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address], data={}
            )

        current_addresses = self._async_current_ids()

        log("async_step_user", f"current_addresses={current_addresses}")
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = KindhomeBluetoothDeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = (
                        device.get_device_name() or discovery_info.name
                )

        if not self._discovered_devices:
            log("async_step_user", "no devices found, aborting!")
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )
