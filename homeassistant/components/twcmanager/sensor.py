"""Platform for sensor integration."""

import logging
import re

from aiohttp.web import HTTPError
import async_timeout

from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLT,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    # assuming API object stored here by __init__.py
    api = hass.data[DOMAIN][entry.entry_id]

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await api.async_get_slave_twcs()
        except HTTPError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=SCAN_INTERVAL,
    )

    #
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for twc in coordinator.data:
        for prop in coordinator.data[twc]:
            if prop in [
                "TWCID",
                "lastHeartbeat",
                # Skip properties retrieved from the car itself via Tesla's API
                "lastBatterySOC",
                "lastChargeLimit",
                "lastAtHome",
                "lastTimeToFullCharge",
            ]:
                continue
            sensors.append(TwcSensor(coordinator, twc, prop))
    async_add_entities(sensors)


class TwcSensor(CoordinatorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, twc, prop):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.twc = twc
        self.prop = prop
        self.entity_id = (
            "sensor." + DOMAIN + "_" + twc + "_" + self.__camel_to_snake(prop)
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return "TWC " + self.twc + " " + self.prop

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.twc][self.prop]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if "amps" in self.entity_id:
            return ELECTRICAL_CURRENT_AMPERE
        elif "volts" in self.entity_id:
            return VOLT
        elif self.entity_id.endswith("_w"):
            return POWER_WATT
        elif "kwh" in self.entity_id:
            return ENERGY_KILO_WATT_HOUR
        else:
            return None

    @property
    def device_class(self):
        """Return the device class."""
        if "amps" in self.entity_id:
            return DEVICE_CLASS_CURRENT
        elif "volts" in self.entity_id:
            return DEVICE_CLASS_VOLTAGE
        elif self.entity_id.endswith("_w"):
            return DEVICE_CLASS_POWER
        elif "kwh" in self.entity_id:
            return DEVICE_CLASS_ENERGY
        else:
            return None

    @property
    def state_class(self):
        """Return the state class."""
        return "measurement"

    @staticmethod
    def __camel_to_snake(name: str):
        name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()
        return name.replace("k_wh", "_kwh")
