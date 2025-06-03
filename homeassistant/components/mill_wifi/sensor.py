import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE, UnitOfPower, UnitOfTemperature, UnitOfEnergy,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_PARTS_PER_BILLION as PPB,
)
from homeassistant.core import HomeAssistant, callback 
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN 
from .device_metric import DeviceMetric
from .device_capability import DEVICE_CAPABILITY_MAP, EDeviceCapability, EDeviceType, EFilterState 
from .coordinator import MillDataCoordinator
from .common_entity import MillEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: dict[EDeviceCapability, tuple[str, str | None, SensorDeviceClass | None, SensorStateClass | None, str | None]] = {
    EDeviceCapability.MEASURE_TEMPERATURE: ("Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, None),
    EDeviceCapability.MEASURE_HUMIDITY: ("Humidity", PERCENTAGE, SensorDeviceClass.HUMIDITY, SensorStateClass.MEASUREMENT, None),
    EDeviceCapability.MEASURE_POWER: ("Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:flash"), 
    EDeviceCapability.MEASURE_DAILY_POWER: ("Daily Energy", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:flash"), 
    EDeviceCapability.MEASURE_TVOC: ("TVOC", PPB, SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS, SensorStateClass.MEASUREMENT, "mdi:molecule"),
    EDeviceCapability.MEASURE_CO2: ("CO2", CONCENTRATION_PARTS_PER_MILLION, SensorDeviceClass.CO2, SensorStateClass.MEASUREMENT, "mdi:molecule-co2"),
    EDeviceCapability.MEASURE_PM1: ("PM1", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.PM1, SensorStateClass.MEASUREMENT, "mdi:dots-hexagon"),
    EDeviceCapability.MEASURE_PM25: ("PM2.5", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.PM25, SensorStateClass.MEASUREMENT, "mdi:dots-hexagon"),
    EDeviceCapability.MEASURE_PM10: ("PM10", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.PM10, SensorStateClass.MEASUREMENT, "mdi:dots-hexagon"),
    EDeviceCapability.MEASURE_PARTICLES: ("Particles", None, SensorDeviceClass.AQI, SensorStateClass.MEASUREMENT, "mdi:blur"),
    EDeviceCapability.MEASURE_BATTERY: ("Battery", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, None),
    EDeviceCapability.MEASURE_WATTAGE: ("Max Heater Power", UnitOfPower.WATT, SensorDeviceClass.POWER, None, "mdi:flash-outline"), 
    EDeviceCapability.MEASURE_FILTER_STATE: ("Filter Status", None, None, None, "mdi:air-filter"), 
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MillDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = []

    if not coordinator.data:
        _LOGGER.warning("No data in coordinator during sensor setup, skipping sensor entity creation.")
        return

    for device_id, device_data in coordinator.data.items():
        if not device_data:
            _LOGGER.warning("Missing data for device ID: %s in sensor setup", device_id)
            continue

        device_type_name = DeviceMetric.get_device_type(device_data)
        if not device_type_name:
            _LOGGER.warning("Could not determine device type for %s when setting up sensors", device_id)
            continue
        
        try:
            device_type_enum = EDeviceType(device_type_name)
        except ValueError:
            _LOGGER.warning("Unsupported device type for sensor platform: '%s' for device %s", device_type_name, device_id)
            continue

        capabilities = DEVICE_CAPABILITY_MAP.get(device_type_enum, set())

        for capability_enum, (name_suffix, unit, device_class, state_class, icon) in SENSOR_TYPES.items(): 
            if capability_enum in capabilities:
                entities.append(
                    MillSensor(
                        coordinator,
                        device_id,
                        capability_enum,
                        name_suffix,
                        unit,
                        device_class,
                        state_class,
                        icon 
                    )
                )
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.info("No sensor entities added for Mill WiFi integration.")

class MillSensor(MillEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillDataCoordinator,
        device_id: str,
        capability: EDeviceCapability,
        name_suffix: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        icon: str | None 
    ):
        super().__init__(coordinator, device_id, capability)
        self.name = name_suffix 

        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon 
        self._attr_native_value = None 
        
        self._update_internal_state() 

    def _update_internal_state(self) -> None:
        if not self._device:
            self._attr_native_value = None
            return

        value = DeviceMetric.get_capability_value(self._device, self._capability)
        new_native_value = None
        
        if value is not None:
            if self._capability == EDeviceCapability.MEASURE_FILTER_STATE: 
                new_native_value = str(value)
            elif self._attr_state_class in [SensorStateClass.MEASUREMENT, SensorStateClass.TOTAL_INCREASING] or \
                self._attr_device_class in [
                    SensorDeviceClass.TEMPERATURE, SensorDeviceClass.HUMIDITY, SensorDeviceClass.POWER,
                    SensorDeviceClass.ENERGY, SensorDeviceClass.CO2, SensorDeviceClass.AQI,
                    SensorDeviceClass.PM1, SensorDeviceClass.PM25, SensorDeviceClass.PM10,
                    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS, SensorDeviceClass.BATTERY
                ]: 
                try:
                    new_native_value = float(value)
                except (ValueError, TypeError):
                    _LOGGER.debug("Could not parse sensor value '%s' as float for %s (%s)", value, self.entity_id, self._capability)
                    new_native_value = None 
            else: 
                new_native_value = value 
        
        if self._attr_native_value != new_native_value:
            self._attr_native_value = new_native_value

    @property
    def native_value(self):
        return self._attr_native_value

    @callback
    def _handle_coordinator_update(self) -> None: 
        self._update_internal_state()
        super()._handle_coordinator_update()
