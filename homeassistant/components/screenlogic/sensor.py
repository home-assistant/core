"""Support for a ScreenLogic Sensor."""
from typing import Any

from screenlogicpy.const import (
    CHEM_DOSING_STATE,
    CODE,
    DATA as SL_DATA,
    DEVICE_TYPE,
    EQUIPMENT,
    STATE_TYPE,
    UNIT,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ScreenlogicDataUpdateCoordinator
from .const import DOMAIN
from .entity import ScreenlogicEntity, ScreenLogicPushEntity

SUPPORTED_BASIC_SENSORS = (
    "air_temperature",
    "saturation",
)

SUPPORTED_BASIC_CHEM_SENSORS = (
    "orp",
    "ph",
)

SUPPORTED_CHEM_SENSORS = (
    "calcium_harness",
    "current_orp",
    "current_ph",
    "cya",
    "orp_dosing_state",
    "orp_last_dose_time",
    "orp_last_dose_volume",
    "orp_setpoint",
    "orp_supply_level",
    "ph_dosing_state",
    "ph_last_dose_time",
    "ph_last_dose_volume",
    "ph_probe_water_temp",
    "ph_setpoint",
    "ph_supply_level",
    "salt_tds_ppm",
    "total_alkalinity",
)

SUPPORTED_SCG_SENSORS = (
    "scg_salt_ppm",
    "scg_super_chlor_timer",
)

SUPPORTED_PUMP_SENSORS = ("currentWatts", "currentRPM", "currentGPM")

SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS = {
    DEVICE_TYPE.DURATION: SensorDeviceClass.DURATION,
    DEVICE_TYPE.ENUM: SensorDeviceClass.ENUM,
    DEVICE_TYPE.ENERGY: SensorDeviceClass.POWER,
    DEVICE_TYPE.POWER: SensorDeviceClass.POWER,
    DEVICE_TYPE.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    DEVICE_TYPE.VOLUME: SensorDeviceClass.VOLUME,
}

SL_STATE_TYPE_TO_HA_STATE_CLASS = {
    STATE_TYPE.MEASUREMENT: SensorStateClass.MEASUREMENT,
    STATE_TYPE.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
}

SL_UNIT_TO_HA_UNIT = {
    UNIT.CELSIUS: UnitOfTemperature.CELSIUS,
    UNIT.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
    UNIT.MILLIVOLT: UnitOfElectricPotential.MILLIVOLT,
    UNIT.WATT: UnitOfPower.WATT,
    UNIT.HOUR: UnitOfTime.HOURS,
    UNIT.SECOND: UnitOfTime.SECONDS,
    UNIT.REVOLUTIONS_PER_MINUTE: REVOLUTIONS_PER_MINUTE,
    UNIT.PARTS_PER_MILLION: CONCENTRATION_PARTS_PER_MILLION,
    UNIT.PERCENT: PERCENTAGE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities: list[ScreenLogicSensorEntity] = []
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    equipment_flags = coordinator.gateway_data[SL_DATA.KEY_CONFIG]["equipment_flags"]

    # Generic push sensors
    for sensor_name in coordinator.gateway_data[SL_DATA.KEY_SENSORS]:
        if sensor_name in SUPPORTED_BASIC_SENSORS:
            entities.append(
                ScreenLogicStatusSensor(coordinator, sensor_name, CODE.STATUS_CHANGED)
            )

        # While these values exist in the chemistry data, their last value doesn't
        # persist there when the pump is off/there is no flow. Pulling them from
        # the basic sensors keeps the 'last' value and is better for graphs.
        if (
            equipment_flags & EQUIPMENT.FLAG_INTELLICHEM
            and sensor_name in SUPPORTED_BASIC_CHEM_SENSORS
        ):
            entities.append(
                ScreenLogicStatusSensor(coordinator, sensor_name, CODE.STATUS_CHANGED)
            )

    # Pump sensors
    for pump_num, pump_data in coordinator.gateway_data[SL_DATA.KEY_PUMPS].items():
        if pump_data["data"] != 0 and "currentWatts" in pump_data:
            for pump_key in pump_data:
                enabled = True
                # Assumptions for Intelliflow VF
                if pump_data["pumpType"] == 1 and pump_key == "currentRPM":
                    enabled = False
                # Assumptions for Intelliflow VS
                if pump_data["pumpType"] == 2 and pump_key == "currentGPM":
                    enabled = False
                if pump_key in SUPPORTED_PUMP_SENSORS:
                    entities.append(
                        ScreenLogicPumpSensor(coordinator, pump_num, pump_key, enabled)
                    )

    # IntelliChem sensors
    if equipment_flags & EQUIPMENT.FLAG_INTELLICHEM:
        for chem_sensor_name in coordinator.gateway_data[SL_DATA.KEY_CHEMISTRY]:
            enabled = True
            if equipment_flags & EQUIPMENT.FLAG_CHLORINATOR:
                if chem_sensor_name in ("salt_tds_ppm",):
                    enabled = False
            if chem_sensor_name in SUPPORTED_CHEM_SENSORS:
                entities.append(
                    ScreenLogicChemistrySensor(
                        coordinator, chem_sensor_name, CODE.CHEMISTRY_CHANGED, enabled
                    )
                )

    # SCG sensors
    if equipment_flags & EQUIPMENT.FLAG_CHLORINATOR:
        entities.extend(
            [
                ScreenLogicSCGSensor(coordinator, scg_sensor)
                for scg_sensor in coordinator.gateway_data[SL_DATA.KEY_SCG]
                if scg_sensor in SUPPORTED_SCG_SENSORS
            ]
        )

    async_add_entities(entities)


class ScreenLogicSensorEntity(ScreenlogicEntity, SensorEntity):
    """Base class for all ScreenLogic sensor entities."""

    _attr_has_entity_name = True

    @property
    def name(self) -> str | None:
        """Name of the sensor."""
        return self.sensor["name"]

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        sl_unit = self.sensor.get("unit")
        return SL_UNIT_TO_HA_UNIT.get(sl_unit, sl_unit)

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Device class of the sensor."""
        device_type = self.sensor.get("device_type")
        return SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(device_type)

    @property
    def entity_category(self) -> EntityCategory | None:
        """Entity Category of the sensor."""
        return (
            None if self._data_key == "air_temperature" else EntityCategory.DIAGNOSTIC
        )

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class of the sensor."""
        state_type = self.sensor.get("state_type")
        if self._data_key == "scg_super_chlor_timer":
            return None
        return SL_STATE_TYPE_TO_HA_STATE_CLASS.get(state_type)

    @property
    def options(self) -> list[str] | None:
        """Return a set of possible options."""
        return self.sensor.get("enum_options")

    @property
    def native_value(self) -> str | int | float:
        """State of the sensor."""
        return self.sensor["value"]

    @property
    def sensor(self) -> dict[str | int, Any]:
        """Shortcut to access the sensor data."""
        return self.gateway_data[SL_DATA.KEY_SENSORS][self._data_key]


class ScreenLogicStatusSensor(ScreenLogicSensorEntity, ScreenLogicPushEntity):
    """Representation of a basic ScreenLogic sensor entity."""


class ScreenLogicPumpSensor(ScreenLogicSensorEntity):
    """Representation of a ScreenLogic pump sensor entity."""

    def __init__(self, coordinator, pump, key, enabled=True):
        """Initialize of the pump sensor."""
        super().__init__(coordinator, f"{key}_{pump}", enabled)
        self._pump_id = pump
        self._key = key

    @property
    def sensor(self) -> dict[str | int, Any]:
        """Shortcut to access the pump sensor data."""
        return self.gateway_data[SL_DATA.KEY_PUMPS][self._pump_id][self._key]


class ScreenLogicChemistrySensor(ScreenLogicSensorEntity, ScreenLogicPushEntity):
    """Representation of a ScreenLogic IntelliChem sensor entity."""

    def __init__(self, coordinator, key, message_code, enabled=True):
        """Initialize of the pump sensor."""
        super().__init__(coordinator, f"chem_{key}", message_code, enabled)
        self._key = key

    @property
    def native_value(self) -> str | int | float:
        """State of the sensor."""
        value = self.sensor["value"]
        if "dosing_state" in self._key:
            return CHEM_DOSING_STATE.NAME_FOR_NUM[value]
        return (value - 1) if "supply" in self._data_key else value

    @property
    def sensor(self) -> dict[str | int, Any]:
        """Shortcut to access the pump sensor data."""
        return self.gateway_data[SL_DATA.KEY_CHEMISTRY][self._key]


class ScreenLogicSCGSensor(ScreenLogicSensorEntity):
    """Representation of ScreenLogic SCG sensor entity."""

    @property
    def sensor(self) -> dict[str | int, Any]:
        """Shortcut to access the pump sensor data."""
        return self.gateway_data[SL_DATA.KEY_SCG][self._data_key]
