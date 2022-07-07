"""The bluetooth integration."""
from __future__ import annotations

import dataclasses
import logging
from typing import Any

from bleak import BleakClient, BleakScanner, BLEDevice

# from homeassistant import config_entries
# from homeassistant.components import websocket_api
# from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.data_entry_flow import BaseServiceInfo

# from homeassistant.helpers import discovery_flow, system_info
# from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# import voluptuous as vol


# from homeassistant.loader import async_get_bluetooth


_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class BluetoothServiceInfo(BaseServiceInfo):
    """Prepared info from bluetooth entries."""

    local_name: str
    manufacturer_data: dict[int, str]
    service_data: dict[str, bytes]
    service_uuids: list[str]
    manufacturer: str | None
    platform_data: Any

    @property
    def hci_packet(self):
        """Return the HCI packet for this service."""
        # TODO:
        return "043E%02X0201%02X%02X%02X%02X%02X%02X%02X%02X%02X%*s%02X"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the bluetooth integration."""
    # bt = await async_get_bluetooth(hass)
    bluetooth = {}
    bluetooth_discovery = BluetoothManager(hass, bluetooth)
    await bluetooth_discovery.async_setup()
    hass.data[DOMAIN] = bluetooth

    # TODO:
    # websocket_api.async_register_command(hass, list_devices)
    # websocket_api.async_register_command(hass, set_devices)

    return True


class BluetoothManager:
    """Manage Bluetooth."""

    def __init__(
        self,
        hass: HomeAssistant,
        bluetooth: list[dict[str, str]],
    ) -> None:
        """Init USB Discovery."""
        self.hass = hass
        self.bluetooth = bluetooth

    async def async_setup(self) -> None:
        """Set up BT Discovery."""
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.async_start)

    async def async_start(self, event: Event) -> None:
        """Start BT Discovery and run a manual scan."""
