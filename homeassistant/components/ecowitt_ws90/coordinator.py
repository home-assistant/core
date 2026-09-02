"""Polling, and what to do when the sensor stops answering."""

from datetime import timedelta
import logging
from typing import override

from ecowitt_ws90_modbus import WS90
from modbus_connection import ModbusError
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type WS90ConfigEntry = ConfigEntry[WS90DataUpdateCoordinator]


class WS90DataUpdateCoordinator(DataUpdateCoordinator[WS90]):
    """Poll the WS90's live weather readings."""

    config_entry: WS90ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WS90ConfigEntry,
        device: WS90,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device

    @cached_property
    def device_info(self) -> DeviceInfo:
        """The one sensor array every entity on this config entry belongs to."""
        info = self.device.info
        return DeviceInfo(
            identifiers={(DOMAIN, f"{info.device_id:08x}")},
            manufacturer=info.manufacturer,
            model=info.model,
        )

    @override
    async def _async_update_data(self) -> WS90:
        try:
            await self.device.async_update()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

        # The address in `entry.data` can end up pointing at a different
        # responder than the one this entry was created for (the gateway is
        # reconfigured, a unit ID is reused, ...). Re-check identity on every
        # poll -- not just at setup -- so a swap mid-run stops publishing the
        # new responder's readings under this entry's entities.
        info = self.device.info
        if (
            info.model != "WS90"
            or f"{info.device_id:08x}" != self.config_entry.unique_id
        ):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unexpected_device",
                translation_placeholders={
                    "unique_id": self.config_entry.unique_id or "unknown"
                },
            )

        return self.device
