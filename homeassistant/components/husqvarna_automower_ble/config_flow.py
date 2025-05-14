"""Config flow for Husqvarna Bluetooth integration."""

from __future__ import annotations

import random
import re
from typing import Any

from automower_ble.mower import Mower
from bleak import BleakError
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID

from .const import DOMAIN, LOGGER


def _is_supported(discovery_info: BluetoothServiceInfo):
    """Check if device is supported."""

    LOGGER.debug(
        "%s manufacturer data: %s",
        discovery_info.address,
        discovery_info.manufacturer_data,
    )

    manufacturer = any(key == 1062 for key in discovery_info.manufacturer_data)
    service_husqvarna = any(
        service == "98bd0001-0b0e-421a-84e5-ddbf75dc6de4"
        for service in discovery_info.service_uuids
    )
    service_generic = any(
        service == "00001800-0000-1000-8000-00805f9b34fb"
        for service in discovery_info.service_uuids
    )

    return manufacturer and service_husqvarna and service_generic


def _check_mac(mac: str) -> str:
    """Verify MAC address format."""
    mac = re.sub("[.:-]", "", mac)
    mac = mac.lower()
    mac = "".join(mac.split())
    assert len(mac) == 12
    assert mac.isalnum()
    return ":".join([f"{mac[i : i + 2]}" for i in range(0, 12, 2)])


class HusqvarnaAutomowerBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Husqvarna Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.address: str | None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""

        LOGGER.debug("Discovered device: %s", discovery_info)
        if not _is_supported(discovery_info):
            return self.async_abort(reason="no_devices_found")

        self.address = discovery_info.address
        await self.async_set_unique_id(self.address)
        self._abort_if_unique_id_configured()
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self.address

        self.address = _check_mac(self.address)

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        channel_id = random.randint(1, 0xFFFFFFFF)

        try:
            (manufacturer, device_type, model) = await Mower(
                channel_id, self.address
            ).probe_gatts(device)
        except (BleakError, TimeoutError) as exception:
            LOGGER.exception("Failed to connect to device: %s", exception)
            return self.async_abort(reason="cannot_connect")

        title = manufacturer + " " + device_type

        LOGGER.debug("Found device: %s", title)

        if user_input is not None:
            return self.async_create_entry(
                title=title,
                data={CONF_ADDRESS: self.address, CONF_CLIENT_ID: channel_id},
            )

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
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self.address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(self.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                },
            ),
        )
