"""Sensor platform of the VARTA Storage integration."""

from datetime import timedelta
import logging

import async_timeout
from vartastorage import vartastorage

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Entry setup which was forwarded by __init__.py."""

    async def async_update_data():
        """Fetch data and preo-process the data from API endpoint."""

        def sync_update():
            """Utilizing synchronous task as the used PyPI Package is not built with async."""
            varta = vartastorage.VartaStorage(entry.data["host"], entry.data["port"])
            # Collect all data from the device at once
            varta.get_all_data()
            return varta

        try:
            async with async_timeout.timeout(10):

                # Call synchronous task to update the sensor values
                result = await hass.async_add_executor_job(sync_update)

                thisdict = {}
                thisdict[0] = {
                    "name": "VARTA state of charge",
                    "state": result.soc,
                    "device_class": "battery",
                    "state_class": "measurement",
                    "unit_of_measurement": "%",
                }
                thisdict[1] = {
                    "name": "VARTA grid power",
                    "state": result.grid_power,
                    "device_class": "power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                }
                thisdict[2] = {
                    "name": "VARTA to_grid power",
                    "state": result.to_grid_power,
                    "device_class": "power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                }
                thisdict[3] = {
                    "name": "VARTA from_grid power",
                    "state": result.from_grid_power,
                    "device_class": "power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                }
                thisdict[4] = {
                    "name": "VARTA state",
                    "state": result.state,
                    "device_class": "None",
                    "state_class": "None",
                    "unit_of_measurement": "",
                }
                thisdict[5] = {
                    "name": "VARTA state text",
                    "state": result.state_text,
                    "device_class": "None",
                    "state_class": "None",
                    "unit_of_measurement": "",
                }
                thisdict[6] = {
                    "name": "VARTA active power",
                    "state": result.active_power,
                    "device_class": "power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                }
                thisdict[7] = {
                    "name": "VARTA apparent power",
                    "state": result.apparent_power,
                    "device_class": "power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                }
                thisdict[8] = {
                    "name": "VARTA charge power",
                    "state": result.charge_power,
                    "device_class": "power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                }
                thisdict[9] = {
                    "name": "VARTA discharge power",
                    "state": result.discharge_power,
                    "device_class": "power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                }
                thisdict[10] = {
                    "name": "VARTA error code",
                    "state": result.error_code,
                    "device_class": "None",
                    "state_class": "None",
                    "unit_of_measurement": "",
                }
                thisdict[11] = {
                    "name": "VARTA production power",
                    "state": result.production_power,
                    "device_class": "power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                }
                thisdict[12] = {
                    "name": "VARTA total production power",
                    "state": result.total_production_power,
                    "device_class": "energy",
                    "state_class": "total_increasing",
                    "unit_of_measurement": "kWh",
                }
                thisdict[13] = {
                    "name": "VARTA total charged energy",
                    "state": result.total_charged_energy,
                    "device_class": "energy",
                    "state_class": "total",
                    "unit_of_measurement": "kWh",
                }

                return thisdict
        except Exception as failed_update:
            raise UpdateFailed("Error communicating with API") from failed_update

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=1),
    )

    #
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        MyEntity(coordinator, idx) for idx, ent in enumerate(coordinator.data)
    )


class MyEntity(CoordinatorEntity, SensorEntity):
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

        self._attr_device_info = DeviceInfo(
            configuration_url="http://" + coordinator.config_entry.data["host"],
            identifiers={(DOMAIN, str(coordinator.config_entry.unique_id))},
            manufacturer="VARTA",
            name="VARTA Battery",
        )

        self._attr_unique_id = coordinator.config_entry.unique_id + "-" + self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.coordinator.data[self.idx]["name"]

    @property
    # pylint: disable=overridden-final-method
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.idx]["state"]

    @property
    def device_class(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.idx]["device_class"]

    @property
    def state_class(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.idx]["state_class"]

    @property
    # pylint: disable=overridden-final-method
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the sensor."""
        return self.coordinator.data[self.idx]["unit_of_measurement"]
