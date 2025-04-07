"""Config flow for IronOS integration."""

from __future__ import annotations

from typing import Any

from habluetooth import BluetoothServiceInfoBleak
import voluptuous as vol

from homeassistant.components.bluetooth.api import async_discovered_service_info
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DISCOVERY_SVC_UUID, DOMAIN


class IronOSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IronOS."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        title = discovery_info.name

        if user_input is not None:
            return self.async_create_entry(title=title, data={})

        self._set_confirm_only()
        placeholders = {"name": title}
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
            title = self._discovered_devices[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=title, data={})

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, True):
            address = discovery_info.address
            if (
                DISCOVERY_SVC_UUID not in discovery_info.service_uuids
                or address in current_addresses
                or address in self._discovered_devices
            ):
                continue
            self._discovered_devices[address] = discovery_info.name

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )
