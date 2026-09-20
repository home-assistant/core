"""Coordinator for Bluetti BT integration."""

from datetime import timedelta
import logging
from typing import Any, override

from bluetti_bt_lib import DeviceReader, DeviceReaderConfig
from bluetti_bt_lib.base_devices import BaseDeviceV1, BaseDeviceV2

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_API_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ENCRYPTION, DOMAIN

type BluettiBtConfigEntry = ConfigEntry[PollingCoordinator]


class PollingCoordinator(DataUpdateCoordinator):
    """Polling coordinator."""

    config_entry: BluettiBtConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: BluettiBtConfigEntry) -> None:
        """Initialize coordinator."""

        self.mac = config_entry.data.get(CONF_ADDRESS)
        mac_str = str(self.mac).replace(":", "")

        super().__init__(
            hass,
            logging.getLogger(f"{__name__}.{mac_str}"),
            config_entry=config_entry,
            name=f"{DOMAIN}.{mac_str}",
            update_interval=timedelta(seconds=60),
        )

        if config_entry.data.get(CONF_API_VERSION) == 1:
            self.device = BaseDeviceV1()
        elif config_entry.data.get(CONF_API_VERSION) == 2:
            self.device = BaseDeviceV2()
        else:
            raise HomeAssistantError("Unknown protocol")

        self.reader = DeviceReader(
            self.mac,
            self.device,
            self.hass.loop.create_future,
            DeviceReaderConfig(
                use_encryption=config_entry.data.get(CONF_ENCRYPTION),
            ),
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from bluetooth device."""

        # Check if device is connected
        if (
            bluetooth.async_address_present(self.hass, str(self.mac), connectable=True)
            is False
        ):
            self.logger.warning("Device not connected")
            self.last_update_success = False
            return {}

        return await self.reader.read()
