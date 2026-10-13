"""Config flow for the Tile BLE integration."""

from typing import Any, override

import probatio

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, TILE_SERVICE_UUID


class TileBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tile BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a Tile that Home Assistant can see."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address].name, data={}
            )

        current_addresses = self._async_current_ids()
        for service_info in async_discovered_service_info(self.hass, connectable=False):
            if (
                service_info.address not in current_addresses
                and TILE_SERVICE_UUID in service_info.service_uuids
            ):
                self._discovered_devices[service_info.address] = service_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Tiles all look alike, so list the closest ones first.
        devices = sorted(
            self._discovered_devices.values(),
            key=lambda service_info: service_info.rssi,
            reverse=True,
        )
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        {
                            service_info.address: (
                                f"{service_info.name} ({service_info.address},"
                                f" {service_info.rssi} dBm)"
                            )
                            for service_info in devices
                        }
                    )
                }
            ),
        )
