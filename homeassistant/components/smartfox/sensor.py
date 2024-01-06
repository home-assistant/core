"""Platform for EVSE Sensor integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class SmartfoxSensorEntityDescription(SensorEntityDescription):
    """Describes Smartfox sensor entity."""


class SmartfoxPowerSensor(SmartfoxSensorEntityDescription):
    """Smartfox Power Sensor Description."""

    def __init__(self, **kwargs):
        """Initialize Smartfox Sensor whit Super."""
        device_class = SensorDeviceClass.POWER
        native_unit_of_measurement = UnitOfPower.WATT
        state_class = SensorStateClass.MEASUREMENT

        super().__init__(
            device_class=device_class,
            native_unit_of_measurement=native_unit_of_measurement,
            state_class=state_class,
            **kwargs,
        )


class SmartfoxEnergySensor(SmartfoxSensorEntityDescription):
    """Smartfox Energy Sensor Description."""

    def __init__(self, **kwargs):
        """Initialize Smartfox Sensor whit Super."""
        device_class = SensorDeviceClass.ENERGY
        native_unit_of_measurement = kwargs.get(
            "native_unit_of_measurement", UnitOfEnergy.WATT_HOUR
        )
        state_class = kwargs.get("state_class", SensorStateClass.MEASUREMENT)
        kwargs.pop("state_class", None)
        kwargs.pop("native_unit_of_measurement", None)
        super().__init__(
            device_class=device_class,
            native_unit_of_measurement=native_unit_of_measurement,
            state_class=state_class,
            **kwargs,
        )


class SmartfoxVoltageSensor(SmartfoxSensorEntityDescription):
    """Smartfox Power Sensor Description."""

    def __init__(self, **kwargs):
        """Initialize Smartfox Sensor whit Super."""
        device_class = SensorDeviceClass.VOLTAGE
        native_unit_of_measurement = UnitOfElectricPotential.VOLT
        state_class = SensorStateClass.MEASUREMENT
        super().__init__(
            device_class=device_class,
            native_unit_of_measurement=native_unit_of_measurement,
            state_class=state_class,
            **kwargs,
        )


class SmartfoxCurrentSensor(SmartfoxSensorEntityDescription):
    """Smartfox Power Sensor Description."""

    def __init__(self, **kwargs):
        """Initialize Smartfox Sensor whit Super."""
        device_class = SensorDeviceClass.CURRENT
        native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        state_class = SensorStateClass.MEASUREMENT
        super().__init__(
            device_class=device_class,
            native_unit_of_measurement=native_unit_of_measurement,
            state_class=state_class,
            **kwargs,
        )


class SmartfoxPowerFactorSensor(SmartfoxSensorEntityDescription):
    """Smartfox Power Sensor Description."""

    def __init__(self, **kwargs):
        """Initialize Smartfox Sensor whit Super."""
        device_class = SensorDeviceClass.POWER_FACTOR
        state_class = SensorStateClass.MEASUREMENT
        super().__init__(
            device_class=device_class,
            state_class=state_class,
            **kwargs,
        )


class SmartfoxTemperatureSensor(SmartfoxSensorEntityDescription):
    """Smartfox Power Sensor Description."""

    def __init__(self, **kwargs):
        """Initialize Smartfox Sensor whit Super."""
        device_class = SensorDeviceClass.TEMPERATURE
        native_unit_of_measurement = UnitOfTemperature.CELSIUS
        state_class = SensorStateClass.MEASUREMENT
        super().__init__(
            device_class=device_class,
            native_unit_of_measurement=native_unit_of_measurement,
            state_class=state_class,
            **kwargs,
        )


SENSOR_DESCRIPTIONS = [
    SmartfoxPowerSensor(
        key="power__value",
        name="Power",
        icon="mdi:transmission-tower",
    ),
    SmartfoxPowerSensor(
        key="pv__value",
        name="PV Power",
        icon="mdi:solar-power-variant-outline",
    ),
    # SmartfoxPowerSensor(
    #     key="effectivePower__value",
    #     name="Effective Power",
    # ),
    SmartfoxPowerSensor(
        key="phase1__power__value", name="Phase 1 Power", icon="mdi:transmission-tower"
    ),
    SmartfoxPowerSensor(
        key="phase2__power__value", name="Phase 2 Power", icon="mdi:transmission-tower"
    ),
    SmartfoxPowerSensor(
        key="phase3__power__value", name="Phase 3 Power", icon="mdi:transmission-tower"
    ),
    SmartfoxEnergySensor(
        key="energy__value",
        name="Energy",
        icon="mdi:home-import-outline",
        state_class=SensorStateClass.TOTAL,
    ),
    SmartfoxEnergySensor(
        key="returnEnergy__value",
        name="Energy Returned",
        icon="mdi:home-export-outline",
        state_class=SensorStateClass.TOTAL,
    ),
    # SmartfoxEnergySensor(
    #     key="apparentEnergy__value",
    #     name="Apparent Energy",
    #     native_unit_of_measurement="kVAh",
    #     state_class=SensorStateClass.TOTAL,
    # ),
    # SmartfoxEnergySensor(
    #     key="effectiveEnergy__value",
    #     name="Effective Energy",
    #     state_class=SensorStateClass.TOTAL,
    # ),
    SmartfoxEnergySensor(
        key="dayEnergy__value",
        name="Day Energy",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmartfoxEnergySensor(
        key="dayReturnEnergy__value",
        name="Day Returned Energy",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # SmartfoxEnergySensor(
    #     key="dayEffectiveEnergy__value",
    #     name="Day Effective Energy",
    #     state_class=SensorStateClass.TOTAL_INCREASING,
    # ),
    SmartfoxVoltageSensor(
        key="phase1__voltage__value",
        name="Phase 1 Voltage",
    ),
    SmartfoxVoltageSensor(
        key="phase2__voltage__value",
        name="Phase 2 Voltage",
    ),
    SmartfoxVoltageSensor(
        key="phase3__voltage__value",
        name="Phase 3 Voltage",
    ),
    SmartfoxCurrentSensor(
        key="phase1__current__value",
        name="Phase 1 Current",
    ),
    SmartfoxCurrentSensor(
        key="phase2__current__value",
        name="Phase 2 Current",
    ),
    SmartfoxCurrentSensor(
        key="phase3__current__value",
        name="Phase 3 Current",
    ),
    # SmartfoxPowerFactorSensor(
    #     key="phase1__powerFactor__value",
    #     name="Phase 1 Power Factor",
    # ),
    # SmartfoxPowerFactorSensor(
    #     key="phase2__powerFactor__value",
    #     name="Phase 2 Power Factor",
    # ),
    # SmartfoxPowerFactorSensor(
    #     key="phase3__powerFactor__value",
    #     name="Phase 3 Power Factor",
    # ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a sensor for each sensor in the SENSOR_DESCRIPTIONS list."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if coordinator.car_charger_enabled:
        SENSOR_DESCRIPTIONS.extend(
            [
                SmartfoxPowerSensor(
                    key="carCharger__value",
                    name="Car Charger Power",
                    icon="mdi:ev-station",
                ),
                SmartfoxEnergySensor(
                    key="carChargerCurrentChargeEnergy__value",
                    name="Car Charger Charge Energy",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    icon="mdi:ev-station",
                ),
                SmartfoxEnergySensor(
                    key="carChargerEnergy__value",
                    name="Car Charger Energy",
                    state_class=SensorStateClass.TOTAL,
                    icon="mdi:ev-station",
                ),
                SmartfoxEnergySensor(
                    key="heatPumpEnergy__value",
                    name="Heat Pump Energy",
                    state_class=SensorStateClass.TOTAL,
                    icon="mdi:heat-pump",
                ),
                SmartfoxEnergySensor(
                    key="heatPumpThermEnergy__value",
                    name="Heat Pump Therm Energy",
                    state_class=SensorStateClass.TOTAL,
                    icon="mdi:heat-pump",
                ),
            ]
        )

    if coordinator.heat_pump_enabled:
        SENSOR_DESCRIPTIONS.extend(
            [
                SmartfoxPowerSensor(
                    key="heatPumpPower__value",
                    name="Heat Pump Power",
                    icon="mdi:heat-pump",
                ),
                SmartfoxPowerSensor(
                    key="heatPumpThermPower__value",
                    name="Heat Pump Therm Power",
                    icon="mdi:heat-pump",
                ),
                SmartfoxEnergySensor(
                    key="heatPumpEnergy__value",
                    name="Heat Pump Energy",
                    state_class=SensorStateClass.TOTAL,
                    icon="mdi:heat-pump",
                ),
                SmartfoxEnergySensor(
                    key="heatPumpThermEnergy__value",
                    name="Heat Pump Therm Energy",
                    state_class=SensorStateClass.TOTAL,
                    icon="mdi:heat-pump",
                ),
            ]
        )

    if coordinator.water_sensors_enabled:
        SENSOR_DESCRIPTIONS.extend(
            [
                SmartfoxTemperatureSensor(
                    key="bufferHot__value",
                    name="Buffer Hot Temperature",
                ),
                SmartfoxTemperatureSensor(
                    key="bufferCold__value",
                    name="Buffer Cold Temperature",
                ),
                SmartfoxTemperatureSensor(
                    key="warmWater__value",
                    name="Warm Water Temperature",
                ),
            ]
        )

    if coordinator.battery_enabled:
        SENSOR_DESCRIPTIONS.extend(
            [
                SmartfoxPowerSensor(
                    key="batteryPower__value",
                    name="Battery Power",
                    icon="mdi:battery-charging-30",
                ),
            ]
        )
    entities = [
        SmartfoxBaseSensor(coordinator, description=description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class SmartfoxBaseSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an OpenEVSE sensor."""

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.smartfox = coordinator.smartfox
        self._device_info = coordinator.device_info
        self._state = None
        self._attr_unique_id = f"{coordinator.name.lower()}_{description.key}"
        self._attr_name = f"{coordinator.name} {description.name}"
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the monitored data from the charger."""
        try:
            attributes = self.entity_description.key.split("__")

            curvalue = self.smartfox
            for attribute in attributes:
                curvalue = getattr(curvalue, attribute)

            self._state = curvalue

            self.async_write_ha_state()
        except (ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._device_info
