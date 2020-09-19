"""Platform for sensor integration."""
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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            pools = await hass.async_add_executor_job(api.get_pools)
            for pool in pools:
                pool["ICO"] = await hass.async_add_executor_job(
                    api.get_ICO_details, pool["id"]
                )
                pool["devices"] = await hass.async_add_executor_job(
                    api.get_last_pool_measures, pool["id"]
                )

            return pools

        except OndiloError as err:
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

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    entities = []
    for poolidx, pool in enumerate(coordinator.data):
        for devidx, dev in enumerate(pool["devices"]):
            entities.append(OndiloICO(coordinator, poolidx, devidx))

    async_add_entities(entities)


class OndiloICO(Entity):
    """Representation of a Sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, poolidx: int, devidx: int):
        """Initialize sensor entity with data from coordinator."""
        self._coordinator = coordinator
        self._devidx = devidx
        self._poolidx = poolidx
        self._unique_id = (
            f"{self._pooldata()['ICO']['serial_number']}-{self._devdata()['data_type']}"
        )
        self._device_name = self._pooldata()["name"]
        self._name = (
            f"{self._device_name} {SENSOR_TYPES[self._devdata()['data_type']][0]}"
        )
        self._device_class = SENSOR_TYPES[self._devdata()["data_type"]][3]
        self._icon = SENSOR_TYPES[self._devdata()["data_type"]][2]
        self._unit = SENSOR_TYPES[self._devdata()["data_type"]][1]

    def _pooldata(self):
        """Get pool data dict."""
        return self._coordinator.data[self._poolidx]

    def _devdata(self):
        """Get device data dict."""
        return self._pooldata()["devices"][self._devidx]

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def name(self):
        """Name of the device."""
        return self._name

    @property
    def state(self):
        """Last value of the device."""
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
        """Name of the device."""
        return self._unit

    @property
    def unique_id(self):
        """Return the unique ID of this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._pooldata()["ICO"]["serial_number"])},
            "name": self._device_name,
            "manufacturer": "Ondilo",
            "model": "ICO",
            "sw_version": self._pooldata()["ICO"]["sw_version"],
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()
