"""Sensor platform for Tessie integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, TessieApi
from .entity import TessieEntity

PARALLEL_UPDATES = 0


DESCRIPTIONS: dict[str, tuple[SensorEntityDescription, ...]] = {
    TessieApi.CHARGE_STATE: (
        SensorEntityDescription(
            key="battery_level",
            translation_key="battery_level",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.BATTERY,
        ),
        SensorEntityDescription(
            key="battery_range",
            translation_key="battery_range",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            device_class=SensorDeviceClass.DISTANCE,
        ),
        SensorEntityDescription(
            key="charge_energy_added",
            translation_key="charge_energy_added",
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
    ),
    TessieApi.DRIVE_STATE: (
        SensorEntityDescription(
            key="speed",
            translation_key="speed",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
            device_class=SensorDeviceClass.SPEED,
        ),
        SensorEntityDescription(
            key="power",
            translation_key="power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="shift_state",
            translation_key="shift_state",
            icon="mdi:car-shift-pattern",
        ),
    ),
    TessieApi.VEHICLE_STATE: (
        SensorEntityDescription(
            key="tpms_pressure_fl",
            translation_key="tpms_pressure_fl",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPressure.BAR,
            suggested_unit_of_measurement=UnitOfPressure.PSI,
            device_class=SensorDeviceClass.PRESSURE,
        ),
        SensorEntityDescription(
            key="tpms_pressure_fr",
            translation_key="tpms_pressure_fr",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPressure.BAR,
            suggested_unit_of_measurement=UnitOfPressure.PSI,
            device_class=SensorDeviceClass.PRESSURE,
        ),
        SensorEntityDescription(
            key="tpms_pressure_rl",
            translation_key="tpms_pressure_rl",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPressure.BAR,
            suggested_unit_of_measurement=UnitOfPressure.PSI,
            device_class=SensorDeviceClass.PRESSURE,
        ),
        SensorEntityDescription(
            key="tpms_pressure_rr",
            translation_key="tpms_pressure_rr",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPressure.BAR,
            suggested_unit_of_measurement=UnitOfPressure.PSI,
            device_class=SensorDeviceClass.PRESSURE,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie sensor platform from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    api_key = entry.data[CONF_ACCESS_TOKEN]

    async_add_entities(
        [
            TessieSensorEntity(api_key, coordinator, vin, category, description)
            for vin, vehicle in coordinator.data.items()
            for category, descriptions in DESCRIPTIONS.items()
            if category in vehicle
            for description in descriptions
            if description.key in vehicle[category]
        ]
    )


class TessieSensorEntity(TessieEntity, SensorEntity):
    """Base class for Tessie metric sensors."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        api_key: str,
        coordinator: DataUpdateCoordinator,
        vin: str,
        category: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(api_key, coordinator, vin, category, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.get()
