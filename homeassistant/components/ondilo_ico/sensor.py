"""Platform for sensor integration."""
import asyncio
from datetime import timedelta
import logging

from ondilo import OndiloError

from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

SENSOR_TYPES = {
    "temperature": [
        "Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "orp": ["Oxydo Reduction Potential", "mV", "mdi:pool", None],
    "ph": ["pH", "", "mdi:pool", None],
    "tds": ["TDS", CONCENTRATION_PARTS_PER_MILLION, "mdi:pool", None],
    "battery": ["Battery", PERCENTAGE, "mdi:battery", DEVICE_CLASS_BATTERY],
    "rssi": [
        "RSSI",
        PERCENTAGE,
        "mdi:wifi-strength-2",
        DEVICE_CLASS_SIGNAL_STRENGTH,
    ],
    "salt": ["Salt", "mg/L", "mdi:pool", None],
}

SCAN_INTERVAL = timedelta(hours=1)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Ondilo ICO sensors."""

    api = hass.data[DOMAIN][entry.entry_id]

    def get_all_pool_data(pool):
        """Add pool details and last measures to pool data."""
        pool["ICO"] = api.get_ICO_details(pool["id"])
        pool["sensors"] = api.get_last_pool_measures(pool["id"])

        return pool

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            pools = await hass.async_add_executor_job(api.get_pools)

            return await asyncio.gather(
                *[
                    hass.async_add_executor_job(get_all_pool_data, pool)
                    for pool in pools
                ]
            )

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


class OndiloICO(CoordinatorEntity):
    """Representation of a Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, poolidx: int, sensor_idx: int
    ):
        """Initialize sensor entity with data from coordinator."""
        super().__init__(coordinator)

        self._poolid = self.coordinator.data[poolidx]["id"]

        pooldata = self._pooldata()
        self._data_type = pooldata["sensors"][sensor_idx]["data_type"]
        self._unique_id = f"{pooldata['ICO']['serial_number']}-{self._data_type}"
        self._device_name = pooldata["name"]
        self._name = f"{self._device_name} {SENSOR_TYPES[self._data_type][0]}"
        self._device_class = SENSOR_TYPES[self._data_type][3]
        self._icon = SENSOR_TYPES[self._data_type][2]
        self._unit = SENSOR_TYPES[self._data_type][1]

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
    def name(self):
        """Name of the sensor."""
        return self._name

    @property
    def state(self):
        """Last value of the sensor."""
        _LOGGER.debug(
            "Retrieving Ondilo sensor %s state value: %s",
            self._name,
            self._devdata()["value"],
        )
        return self._devdata()["value"]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the Unit of the sensor's measurement."""
        return self._unit

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
