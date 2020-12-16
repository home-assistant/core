"""Platform for sensor integration."""
from datetime import timedelta
import logging

import async_timeout
from niu import NiuAPIException

from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the sensor platform."""
    entities = []

    # Get Niu Api Object
    niu_api = hass.data[DOMAIN][config.entry_id]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                await niu_api.update_vehicles()
                return niu_api.get_vehicles()
        except NiuAPIException as ex:
            raise UpdateFailed(f"Error communicating with API: {ex}") from ex

    # Create coordinator that is used to update all the data
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=60),
    )

    # Fetch initial data so we have data when entities subscribe / Get all scooters from Niu API
    await coordinator.async_refresh()

    # Get all scooters from Niu API and add the entities to the entity list
    for serno, vehicle in coordinator.data.items():
        _LOGGER.info("Found Niu vehicle: %s", vehicle.name)

        # Adding various sensors
        entities.append(NiuOdoMeter(coordinator, serno))
        entities.append(NiuRange(coordinator, serno))

        # Niu vehicles can contain multiple batteries
        for bat_idx in range(0, vehicle.battery_count):
            # Add the charge and temp to the entities
            entities.append(NiuBatteryCharge(coordinator, serno, bat_idx))
            entities.append(NiuBatteryTemp(coordinator, serno, bat_idx))

    # Add all entities
    async_add_entities(entities)

    return True


class NiuEntity(CoordinatorEntity, Entity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx

    @property
    def vehicle(self):
        """Return the Vehicle."""
        return self.coordinator.data[self.idx]

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.vehicle.serial_number)
            },
            "name": self.vehicle.name,
            "manufacturer": "Niu",
            "model": self.vehicle.model,
            "sw_version": self.vehicle.firmware_version,
            "via_device": (DOMAIN, self.vehicle.serial_number),
        }


class NiuOdoMeter(NiuEntity):
    """Represents the ODO meter of a Niu Scooter."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.vehicle.name} ODO Meter"

    @property
    def unique_id(self):
        """Return unique ID."""
        return f"{self.vehicle.serial_number}-ODO-METER"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.vehicle.odometer

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return LENGTH_KILOMETERS


class NiuBatteryCharge(NiuEntity):
    """Represents the Battery Charge of a Niu Scooter."""

    def __init__(self, coordinator, idx, battidx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, idx)
        self.battery_index = battidx
        self.battery_compartments = ["A", "B"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return (
            f"{self.vehicle.name} Charge (Compartment "
            + self.battery_compartments[self.battery_index]
            + ")"
        )

    @property
    def unique_id(self):
        """Return unique ID."""
        return (
            f"{self.vehicle.serial_number}-CHARGE-COMP-"
            + self.battery_compartments[self.battery_index]
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.vehicle.soc(self.battery_index)

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE


class NiuBatteryTemp(NiuEntity):
    """Represents the Battery Temperature of a Niu Scooter."""

    def __init__(self, coordinator, idx, battidx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, idx)
        self.battery_index = battidx
        self.battery_compartments = ["A", "B"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return (
            f"{self.vehicle.name} Temp (Compartment "
            + self.battery_compartments[self.battery_index]
            + ")"
        )

    @property
    def unique_id(self):
        """Return unique ID."""
        return (
            f"{self.vehicle.serial_number}-TEMP-COMP-"
            + self.battery_compartments[self.battery_index]
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.vehicle.battery_temp(self.battery_index)

    @property
    def device_state_attributes(self):
        """Return extra information."""
        return {
            "temperature_description": self.vehicle.battery_temp_desc(
                self.battery_index
            )
        }

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS


class NiuRange(NiuEntity):
    """Represents the Range indicator of a Niu Scooter."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.vehicle.name} Range"

    @property
    def unique_id(self):
        """Return unique ID."""
        return f"{self.vehicle.serial_number}-RANGE"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.vehicle.range

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return LENGTH_KILOMETERS
