"""IoTaWatt DataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, SIGNAL_ADD_DEVICE

_LOGGER = logging.getLogger(__name__)


class IotawattUpdater(DataUpdateCoordinator):
    """Class to manage fetching update data from the IoTaWatt Energy Device."""

    def __init__(self, hass: HomeAssistant, api: str, name: str) -> None:
        """Initialize IotaWattUpdater object."""
        self.api = api
        self.sensorlist: dict[str, list[str]] = {}

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self):
        """Fetch sensors from IoTaWatt device."""

        await self.api.update()
        sensors = self.api.getSensors()

        for sensor in sensors["sensors"]:
            if sensor not in self.sensorlist:
                to_add = {
                    "entity": sensor,
                    "mac_address": sensors["sensors"][sensor].hub_mac_address,
                    "name": sensors["sensors"][sensor].getName(),
                    "unit": sensors["sensors"][sensor].getUnit(),
                }
                async_dispatcher_send(self.hass, SIGNAL_ADD_DEVICE, to_add)
                self.sensorlist[sensor] = sensors["sensors"][sensor]

        return sensors
