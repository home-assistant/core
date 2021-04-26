"""Support for a ScreenLogic Sensor."""
import logging

from screenlogicpy.const import (
    CHEM_DOSING_STATE,
    DATA as SL_DATA,
    DEVICE_TYPE,
    EQUIPMENT,
)

from homeassistant.components.sensor import (
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    SensorEntity,
)

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORTED_CHEM_SENSORS = (
    "calcium_harness",
    "current_orp",
    "current_ph",
    "cya",
    "orp_dosing_state",
    "orp_last_dose_time",
    "orp_last_dose_volume",
    "orp_setpoint",
    "ph_dosing_state",
    "ph_last_dose_time",
    "ph_last_dose_volume",
    "ph_probe_water_temp",
    "ph_setpoint",
    "total_alkalinity",
)

SUPPORTED_SCG_SENSORS = (
    "scg_level1",
    "scg_level2",
    "scg_salt_ppm",
    "scg_super_chlor_timer",
)

SUPPORTED_PUMP_SENSORS = ("currentWatts", "currentRPM", "currentGPM")

SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS = {
    DEVICE_TYPE.TEMPERATURE: DEVICE_CLASS_TEMPERATURE,
    DEVICE_TYPE.ENERGY: DEVICE_CLASS_POWER,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Generic sensors
    for sensor in coordinator.data[SL_DATA.KEY_SENSORS]:
        if sensor == "chem_alarm":
            continue
        if coordinator.data[SL_DATA.KEY_SENSORS][sensor]["value"] != 0:
            entities.append(ScreenLogicSensor(coordinator, sensor))

    # Pump sensors
    for pump in coordinator.data[SL_DATA.KEY_PUMPS]:
        if (
            coordinator.data[SL_DATA.KEY_PUMPS][pump]["data"] != 0
            and "currentWatts" in coordinator.data[SL_DATA.KEY_PUMPS][pump]
        ):
            entities.extend(
                ScreenLogicPumpSensor(coordinator, pump, pump_key)
                for pump_key in coordinator.data[SL_DATA.KEY_PUMPS][pump]
                if pump_key in SUPPORTED_PUMP_SENSORS
            )

    # IntelliChem sensors
    if (
        coordinator.data[SL_DATA.KEY_CONFIG]["equipment_flags"]
        & EQUIPMENT.FLAG_INTELLICHEM
    ):
        entities.extend(
            [
                ScreenLogicChemistrySensor(coordinator, chem_sensor)
                for chem_sensor in coordinator.data[SL_DATA.KEY_CHEMISTRY]
                if chem_sensor in SUPPORTED_CHEM_SENSORS
            ]
        )

    # SCG sensors
    if (
        coordinator.data[SL_DATA.KEY_CONFIG]["equipment_flags"]
        & EQUIPMENT.FLAG_CHLORINATOR
    ):
        entities.extend(
            [
                ScreenLogicSCGSensor(coordinator, scg_sensor)
                for scg_sensor in coordinator.data[SL_DATA.KEY_SCG]
                if scg_sensor in SUPPORTED_SCG_SENSORS
            ]
        )

    async_add_entities(entities)


class ScreenLogicSensor(ScreenlogicEntity, SensorEntity):
    """Representation of the basic ScreenLogic sensor entity."""

    @property
    def name(self):
        """Name of the sensor."""
        return f"{self.gateway_name} {self.sensor['name']}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.sensor.get("unit")

    @property
    def device_class(self):
        """Device class of the sensor."""
        device_type = self.sensor.get("device_type")
        return SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(device_type)

    @property
    def state(self):
        """State of the sensor."""
        value = self.sensor["value"]
        return (value - 1) if "supply" in self._data_key else value

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.coordinator.data[SL_DATA.KEY_SENSORS][self._data_key]


class ScreenLogicPumpSensor(ScreenLogicSensor):
    """Representation of a ScreenLogic pump sensor entity."""

    def __init__(self, coordinator, pump, key):
        """Initialize of the pump sensor."""
        super().__init__(coordinator, f"{key}_{pump}")
        self._pump_id = pump
        self._key = key

    @property
    def sensor(self):
        """Shortcut to access the pump sensor data."""
        return self.coordinator.data[SL_DATA.KEY_PUMPS][self._pump_id][self._key]


class ScreenLogicChemistrySensor(ScreenLogicSensor):
    """Representation of a ScreenLogic IntelliChem sensor entity."""

    def __init__(self, coordinator, key):
        """Initialize of the pump sensor."""
        super().__init__(coordinator, f"chem_{key}")
        self._key = key

    @property
    def state(self):
        """State of the sensor."""
        value = self.sensor["value"]
        return (
            CHEM_DOSING_STATE.NAME_FOR_NUM[value]
            if "dosing_state" in self._key
            else value
        )

    @property
    def sensor(self):
        """Shortcut to access the pump sensor data."""
        return self.coordinator.data[SL_DATA.KEY_CHEMISTRY][self._key]


class ScreenLogicSCGSensor(ScreenLogicSensor):
    """Representation of ScreenLogic SCG sensor entity."""

    @property
    def sensor(self):
        """Shortcut to access the pump sensor data."""
        return self.coordinator.data[SL_DATA.KEY_SCG][self._data_key]
