"""Config flow for melnor."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for melnor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_address: str

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered device."""

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_address,
                data={
                    CONF_ADDRESS: self._discovered_address,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovered_address},
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initialized by Bluetooth discovery."""

        address = discovery_info.address

        self._async_abort_entries_match({CONF_ADDRESS: address})

        await self.async_set_unique_id(address)

        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: address})

        self._discovered_address = address

        self.context["title_placeholders"] = {"name": address}
        return await self.async_step_bluetooth_confirm()
