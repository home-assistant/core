"""BleBox sensor entities."""

from datetime import datetime, timedelta

import blebox_uniapi.sensor

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BleBoxConfigEntry
from .entity import BleBoxEntity

SCAN_INTERVAL = timedelta(seconds=5)


SENSOR_TYPES = (
    SensorEntityDescription(
        key="pm1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="pm2_5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="powerConsumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:lightning-bolt",
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="wind",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    ),
    SensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    SensorEntityDescription(
        key="forwardActiveEnergy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    SensorEntityDescription(
        key="reverseActiveEnergy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    SensorEntityDescription(
        key="reactivePower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    ),
    SensorEntityDescription(
        key="activePower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="apparentPower",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
    ),
    SensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
    ),
    SensorEntityDescription(
        key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
)

TOTAL_ENERGY_DESCRIPTION = SensorEntityDescription(
    key="totalEnergy",
    device_class=SensorDeviceClass.ENERGY,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    state_class=SensorStateClass.TOTAL,
)

_MAX_ELAPSED_S = 30


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a BleBox entry."""
    sensors = config_entry.runtime_data.features.get("sensors", [])
    entities: list[BleBoxSensorEntity | BleBoxEnergySensor] = [
        BleBoxSensorEntity(feature, description)
        for feature in sensors
        for description in SENSOR_TYPES
        if description.key == feature.device_class
    ]
    entities += [
        BleBoxEnergySensor(feature, TOTAL_ENERGY_DESCRIPTION)
        for feature in sensors
        if feature.device_class == "activePower"
        and feature.product.type in ("switchBox", "switchBoxD")
    ]
    async_add_entities(entities, True)


class BleBoxSensorEntity(BleBoxEntity[blebox_uniapi.sensor.BaseSensor], SensorEntity):
    """Representation of a BleBox sensor feature."""

    def __init__(
        self,
        feature: blebox_uniapi.sensor.BaseSensor,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a BleBox sensor feature."""
        super().__init__(feature)
        self.entity_description = description

    @property
    def native_value(self):
        """Return the state."""
        return self._feature.native_value

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if implemented."""
        if self.state_class != SensorStateClass.TOTAL:
            return None
        native_implementation = getattr(self._feature, "last_reset", None)
        return native_implementation or super().last_reset


class BleBoxEnergySensor(BleBoxEntity[blebox_uniapi.sensor.BaseSensor], RestoreSensor):
    """Energy sensor that accumulates kWh from activePower using the trapezoidal rule."""

    def __init__(
        self,
        feature: blebox_uniapi.sensor.BaseSensor,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(feature)
        self.entity_description = description
        self._attr_unique_id = f"{feature.unique_id}-totalenergy"
        self._attr_name = f"{feature.product.name} ({feature.product.type}#totalEnergy)"
        self._energy: float = 0.0
        self._last_power_w: float | None = None
        self._last_update: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Restore accumulated energy on restart."""
        await super().async_added_to_hass()
        if last_data := await self.async_get_last_sensor_data():
            if last_data.native_value is not None:
                self._energy = float(str(last_data.native_value))

    @property
    def native_value(self) -> StateType:
        """Return accumulated energy in kWh."""
        return self._energy

    async def async_update(self) -> None:
        """Accumulate energy using trapezoidal integration of activePower."""
        await super().async_update()

        power_w = self._feature.native_value
        now = dt_util.utcnow()

        if power_w is None:
            self._last_power_w = None
            self._last_update = None
            return

        if self._last_update is None:
            self._last_power_w = power_w
            self._last_update = now
            return

        elapsed_s = (now - self._last_update).total_seconds()

        if elapsed_s > _MAX_ELAPSED_S:
            self._last_power_w = power_w
            self._last_update = now
            return

        avg_power = (self._last_power_w + power_w) / 2
        self._energy += avg_power * elapsed_s / 3_600_000

        self._last_power_w = power_w
        self._last_update = now
