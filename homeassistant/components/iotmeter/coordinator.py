"""Module for IoTMeter integration in Home Assistant."""

from datetime import timedelta
import logging
from typing import Any

from iotmeter_api import IoTMeterAPI, IotMeterAPIError

from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

# from .number import ChargingCurrentNumber
from .sensor import (
    ConsumptionEnergySensor,
    EvseSensor,
    GenerationEnergySensor,
    TotalPowerSensor,
)

SCAN_INTERVAL = 5
_LOGGER = logging.getLogger(__name__)


class IotMeterDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the IotMeter API."""

    def __init__(self, hass, ip_address, port):
        """Initialize the data update coordinator."""
        self.ip_address = ip_address
        self.port = port
        self.setting_read: bool = False
        self.async_add_sensor_entities = None
        self.async_add_number_entities = None
        self.entities = []
        self.number_of_evse: int = 0
        self.is_smartmodul = None
        self.api = IoTMeterAPI(ip_address, port)
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=SCAN_INTERVAL)
        )

    def update_ip_port(self, ip_address, port):
        """Update IP address and port."""
        self.ip_address = ip_address
        self.port = port
        self.api = IoTMeterAPI(ip_address, port)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        data: dict[str, Any] = {}
        try:
            data = await self.api.fetch_all_data(self.is_smartmodul)
            number_of_evse = data.get("NUMBER_OF_EVSE", 0)

            if "TYPE" in data:
                if data["TYPE"] == "2":
                    self.is_smartmodul = True
            elif "inp,EVSE1" in data:
                self.is_smartmodul = False

            if not self.setting_read or (
                self.number_of_evse != number_of_evse and self.setting_read
            ):
                self.number_of_evse = number_of_evse
                await self.remove_entities()
                if self.async_add_sensor_entities:
                    self.setting_read = True
                    await self.add_sensor_entities()

        except IotMeterAPIError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        return data

    async def add_sensor_entities(self):
        """Add sensor entities to Home Assistant."""
        translations = await async_get_translations(
            self.hass, self.hass.config.language, "entity"
        )
        self.entities = [
            ConsumptionEnergySensor(
                self, "Total Consumption Energy", translations, "kWh"
            ),
            TotalPowerSensor(self, "Total Power", translations, "kW"),
        ]
        if not self.is_smartmodul:
            self.entities.append(
                GenerationEnergySensor(
                    self, "Total Generation Energy", translations, "kWh"
                )
            )
        if self.number_of_evse > 0 or self.is_smartmodul:
            self.entities.append(
                EvseSensor(
                    self, "Evse", translations, "", smartmodule=self.is_smartmodul
                )
            )
        self.async_add_sensor_entities(self.entities)

    async def remove_entities(self):
        """Remove entities."""
        if self.entities:
            _LOGGER.debug("Removing entities: %s", self.entities)
            for entity in self.entities:
                await entity.async_remove()
            self.entities = []
