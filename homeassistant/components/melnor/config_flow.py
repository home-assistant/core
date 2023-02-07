"""Config flow for melnor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, MANUFACTURER_DATA_START, MANUFACTURER_ID


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for melnor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_address: str
        self._discovered_addresses: list[str] = []

    def _create_entry(self, address: str) -> FlowResult:
        """Create an entry for a discovered device."""

        return self.async_create_entry(
            title=address,
            data={
                CONF_ADDRESS: address,
            },
        )

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered device."""

        if user_input is not None:
            return self._create_entry(self._discovered_address)

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovered_address},
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initialized by Bluetooth discovery."""

        address = discovery_info.address

        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: address})

        self._discovered_address = address

        self.context["title_placeholders"] = {"name": address}
        return await self.async_step_bluetooth_confirm()

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to pick discovered device."""

        if user_input is not None:
            address = user_input[CONF_ADDRESS]

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self._create_entry(address)

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(
            self.hass, connectable=True
        ):
            if discovery_info.manufacturer_id == MANUFACTURER_ID and any(
                manufacturer_data.startswith(MANUFACTURER_DATA_START)
                for manufacturer_data in discovery_info.manufacturer_data.values()
            ):
                address = discovery_info.address
                if (
                    address not in current_addresses
                    and address not in self._discovered_addresses
                ):
                    self._discovered_addresses.append(address)

        addresses = {
            address
            for address in self._discovered_addresses
            if address not in current_addresses
        }

        # Check if there is at least one device
        if not addresses:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(addresses)}),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        return await self.async_step_pick_device()
