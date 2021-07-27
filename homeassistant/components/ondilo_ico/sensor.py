"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import NamedTuple

from ondilo import OndiloError

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN


class OndiloIOCSensorMetadata(NamedTuple):
    """Sensor metadata for an individual Ondilo IOC sensor."""

    name: str
    unit_of_measurement: str | None
    icon: str | None
    device_class: str | None


SENSOR_TYPES: dict[str, OndiloIOCSensorMetadata] = {
    "temperature": OndiloIOCSensorMetadata(
        "Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    "orp": OndiloIOCSensorMetadata(
        "Oxydo Reduction Potential",
        unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        device_class=None,
    ),
    "ph": OndiloIOCSensorMetadata(
        "pH",
        unit_of_measurement=None,
        icon="mdi:pool",
        device_class=None,
    ),
    "tds": OndiloIOCSensorMetadata(
        "TDS",
        unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:pool",
        device_class=None,
    ),
    "battery": OndiloIOCSensorMetadata(
        "Battery",
        unit_of_measurement=PERCENTAGE,
        icon=None,
        device_class=DEVICE_CLASS_BATTERY,
    ),
    "rssi": OndiloIOCSensorMetadata(
        "RSSI",
        unit_of_measurement=PERCENTAGE,
        icon=None,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
    ),
    "salt": OndiloIOCSensorMetadata(
        "Salt",
        unit_of_measurement="mg/L",
        icon="mdi:pool",
        device_class=None,
    ),
}

SCAN_INTERVAL = timedelta(hours=1)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Ondilo ICO sensors."""

    api = hass.data[DOMAIN][entry.entry_id]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            return await hass.async_add_executor_job(api.get_all_pools_data)

        except OndiloError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=SCAN_INTERVAL,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    entities = []
    for poolidx, pool in enumerate(coordinator.data):
        for sensor_idx, sensor in enumerate(pool["sensors"]):
            if sensor["data_type"] in SENSOR_TYPES:
                entities.append(OndiloICO(coordinator, poolidx, sensor_idx))

    async_add_entities(entities)


class OndiloICO(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, poolidx: int, sensor_idx: int
    ) -> None:
        """Initialize sensor entity with data from coordinator."""
        super().__init__(coordinator)

        self._poolid = self.coordinator.data[poolidx]["id"]

        pooldata = self._pooldata()
        self._data_type = pooldata["sensors"][sensor_idx]["data_type"]
        self._unique_id = f"{pooldata['ICO']['serial_number']}-{self._data_type}"
        self._device_name = pooldata["name"]
        metadata = SENSOR_TYPES[self._data_type]
        self._name = f"{self._device_name} {metadata.name}"
        self._attr_device_class = metadata.device_class
        self._attr_icon = metadata.icon
        self._attr_unit_of_measurement = metadata.unit_of_measurement

    def _pooldata(self):
        """Get pool data dict."""
        return next(
            (pool for pool in self.coordinator.data if pool["id"] == self._poolid),
            None,
        )

    def _devdata(self):
        """Get device data dict."""
        return next(
            (
                data_type
                for data_type in self._pooldata()["sensors"]
                if data_type["data_type"] == self._data_type
            ),
            None,
        )

    @property
    def state(self):
        """Last value of the sensor."""
        return self._devdata()["value"]

    @property
    def unique_id(self):
        """Return the unique ID of this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        pooldata = self._pooldata()
        return {
            "identifiers": {(DOMAIN, pooldata["ICO"]["serial_number"])},
            "name": self._device_name,
            "manufacturer": "Ondilo",
            "model": "ICO",
            "sw_version": pooldata["ICO"]["sw_version"],
        }
