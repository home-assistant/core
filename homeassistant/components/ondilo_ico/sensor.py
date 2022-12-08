"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from ondilo import OndiloError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="orp",
        name="Oxydo Reduction Potential",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ph",
        name="pH",
        icon="mdi:pool",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tds",
        name="TDS",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:pool",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon=None,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rssi",
        name="RSSI",
        native_unit_of_measurement=PERCENTAGE,
        icon=None,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="salt",
        name="Salt",
        native_unit_of_measurement="mg/L",
        icon="mdi:pool",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
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
        entities.extend(
            [
                OndiloICO(coordinator, poolidx, description)
                for sensor in pool["sensors"]
                for description in SENSOR_TYPES
                if description.key == sensor["data_type"]
            ]
        )

    async_add_entities(entities)


class OndiloICO(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        poolidx: int,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize sensor entity with data from coordinator."""
        super().__init__(coordinator)
        self.entity_description = description

        self._poolid = self.coordinator.data[poolidx]["id"]

        pooldata = self._pooldata()
        self._attr_unique_id = f"{pooldata['ICO']['serial_number']}-{description.key}"
        self._device_name = pooldata["name"]
        self._attr_name = f"{self._device_name} {description.name}"

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
                if data_type["data_type"] == self.entity_description.key
            ),
            None,
        )

    @property
    def native_value(self):
        """Last value of the sensor."""
        return self._devdata()["value"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for the sensor."""
        pooldata = self._pooldata()
        return DeviceInfo(
            identifiers={(DOMAIN, pooldata["ICO"]["serial_number"])},
            manufacturer="Ondilo",
            model="ICO",
            name=self._device_name,
            sw_version=pooldata["ICO"]["sw_version"],
        )
