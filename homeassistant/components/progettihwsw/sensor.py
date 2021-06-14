"""Control binary sensor instances."""

import asyncio
from datetime import timedelta
import logging

from ProgettiHWSW.analog import AnalogInput
from ProgettiHWSW.temperature import Temperature
import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import setup_analog, setup_temperature
from .const import DEFAULT_POLLING_INTERVAL_SEC, DOMAIN

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the binary sensors from a config entry."""
    board_api = hass.data[DOMAIN][config_entry.entry_id]
    temperatures = config_entry.data["temps"]
    analogs = config_entry.data["analogs"]
    is_rfid = config_entry.data["rfid"]
    sensors = []

    async def async_update_data():
        """Fetch data from API endpoint of board."""
        try:
            async with async_timeout.timeout(5):
                temps = await board_api.get_temps()
                pots = await board_api.get_pots()
                if is_rfid:
                    rfid = await board_api.get_rfid()
                return {
                    "temps": temps,
                    "pots": pots,
                    "rfid": rfid if is_rfid else '0'
                }
        except asyncio.TimeoutError:
            return False

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_POLLING_INTERVAL_SEC),
    )
    await coordinator.async_refresh()

    for i in temperatures:
        sensors.append(
            ProgettihwswTemperature(
                coordinator,
                f"Temperature #{i}",
                board_api.create_unique_id(i, "temperature"),
                setup_temperature(board_api, int(i)),
            )
        )

    for i in analogs:
        sensors.append(
            ProgettihwswAnalog(
                coordinator,
                f"Analog #{i}",
                board_api.create_unique_id(i, "analog"),
                setup_analog(board_api, int(i)),
            )
        )

    if is_rfid is True:
        sensors.append(
            ProgettihwswRFID(
                coordinator,
                "RFID Number",
                board_api.create_unique_id(1, "rfid"),
            )
        )

    async_add_entities(sensors)


class ProgettihwswTemperature(CoordinatorEntity, SensorEntity):
    """Represent a temperature sensor."""

    def __init__(self, coordinator, name, unique_id, sensor: Temperature):
        """Set initializing values."""
        super().__init__(coordinator)
        self._name = name
        self._sensor = sensor
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the sensor name."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return TEMP_CELSIUS

    @property
    def unique_id(self):
        """Return a base64 encoded unique id number."""
        return self._unique_id

    @property
    def state(self):
        """Get sensor state."""
        if self.coordinator.data["temps"] is False:
            return False

        return self.coordinator.data["temps"][str(self._sensor.id)]


class ProgettihwswAnalog(CoordinatorEntity, SensorEntity):
    """Represent a temperature sensor."""

    def __init__(self, coordinator, name, unique_id, sensor: AnalogInput):
        """Set initializing values."""
        super().__init__(coordinator)
        self._name = name
        self._sensor = sensor
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the sensor name."""
        return self._name

    @property
    def unique_id(self):
        """Return a base64 encoded unique id number."""
        return self._unique_id

    @property
    def state(self):
        """Get sensor state."""
        if self.coordinator.data["pots"] is False:
            return False

        return self.coordinator.data["pots"][str(self._sensor.id)]


class ProgettihwswRFID(CoordinatorEntity, SensorEntity):
    """Represent a RFID sensor."""

    def __init__(self, coordinator, name, unique_id):
        """Set initializing values."""
        super().__init__(coordinator)
        self._name = name
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the sensor name."""
        return self._name

    @property
    def unique_id(self):
        """Return a base64 encoded unique id number."""
        return self._unique_id

    @property
    def state(self):
        """Get sensor state."""
        if self.coordinator.data["rfid"] is False:
            return False

        return self.coordinator.data["rfid"]
