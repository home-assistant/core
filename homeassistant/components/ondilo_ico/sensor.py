"""Platform for sensor integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OndiloIcoCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="orp",
        translation_key="oxydo_reduction_potential",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ph",
        translation_key="ph",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tds",
        translation_key="tds",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="salt",
        translation_key="salt",
        native_unit_of_measurement="mg/L",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Ondilo ICO sensors."""

    coordinator: OndiloIcoCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        OndiloICO(coordinator, poolidx, description)
        for poolidx, pool in enumerate(coordinator.data)
        for sensor in pool["sensors"]
        for description in SENSOR_TYPES
        if description.key == sensor["data_type"]
    )


class OndiloICO(CoordinatorEntity[OndiloIcoCoordinator], SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OndiloIcoCoordinator,
        poolidx: int,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize sensor entity with data from coordinator."""
        super().__init__(coordinator)
        self.entity_description = description

        self._poolid = self.coordinator.data[poolidx]["id"]

        pooldata = self._pooldata()
        self._attr_unique_id = f"{pooldata['ICO']['serial_number']}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pooldata["ICO"]["serial_number"])},
            manufacturer="Ondilo",
            model="ICO",
            name=pooldata["name"],
            sw_version=pooldata["ICO"]["sw_version"],
        )

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
