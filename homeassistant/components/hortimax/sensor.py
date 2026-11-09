"""Sensor platform: one sensor per HortOS readout."""

from dataclasses import replace
from datetime import datetime, timedelta
from math import isfinite
from typing import Final, override

from aiohortos import (
    Readout,
    ReadoutValueType,
    decode_cardinal_wind_direction,
    readout_display_name,
    readout_subject,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfConductivity,
    UnitOfEnergy,
    UnitOfIrradiance,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DIMENSIONLESS_UNITS,
    READOUT_ICONS,
    SECONDS_PER_DAY,
    TIME_OF_DAY_READOUTS,
    UNIT_MAP,
    WIND_DIRECTION_SUBJECT,
)
from .coordinator import HortimaxConfigEntry, HortimaxCoordinator
from .entity import HortimaxEntity

PARALLEL_UPDATES = 0


# Everything that follows from the unit alone. Device classes that also need
# the readout identifier or its source (humidity, CO2, wind, gas) are set
# below in `_describe`. Precision is display only, and needs a default
# because the API emits float32-converted doubles (90.15303039550781 %).
UNIT_DESCRIPTIONS: Final[dict[str, SensorEntityDescription]] = {
    unit: SensorEntityDescription(
        key=unit,
        native_unit_of_measurement=unit,
        device_class=device_class,
        suggested_display_precision=precision,
    )
    for unit, device_class, precision in (
        (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 1),
        (UnitOfTemperature.FAHRENHEIT, SensorDeviceClass.TEMPERATURE, 1),
        (UnitOfTemperature.KELVIN, SensorDeviceClass.TEMPERATURE, 1),
        (PERCENTAGE, None, 1),
        ("g/kg", None, 1),
        ("g/m³", None, 1),
        ("J/cm²", None, 1),
        ("J/m²", None, 0),
        (UnitOfSpeed.METERS_PER_SECOND, None, 1),
        (UnitOfSpeed.KILOMETERS_PER_HOUR, None, 1),
        (UnitOfVolumeFlowRate.LITERS_PER_MINUTE, SensorDeviceClass.VOLUME_FLOW_RATE, 1),
        (
            UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            SensorDeviceClass.VOLUME_FLOW_RATE,
            1,
        ),
        ("l/m²", None, 1),
        ("ml/m²", None, 0),
        (UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, 2),
        (UnitOfVolume.CUBIC_METERS, None, 2),
        (UnitOfVolume.LITERS, None, 1),
        (UnitOfVolume.MILLILITERS, None, 0),
        (UnitOfTime.SECONDS, SensorDeviceClass.DURATION, 0),
        (UnitOfTime.MINUTES, SensorDeviceClass.DURATION, 0),
        (UnitOfTime.HOURS, SensorDeviceClass.DURATION, 1),
        (UnitOfIrradiance.WATTS_PER_SQUARE_METER, SensorDeviceClass.IRRADIANCE, 0),
        (UnitOfRatio.PARTS_PER_MILLION, None, 0),
        (LIGHT_LUX, SensorDeviceClass.ILLUMINANCE, 0),
        (UnitOfConductivity.MILLISIEMENS_PER_CM, SensorDeviceClass.CONDUCTIVITY, 2),
        (UnitOfConductivity.MICROSIEMENS_PER_CM, SensorDeviceClass.CONDUCTIVITY, 0),
        (UnitOfPressure.BAR, SensorDeviceClass.PRESSURE, 2),
        (UnitOfPressure.MBAR, SensorDeviceClass.PRESSURE, 0),
        (UnitOfPressure.HPA, SensorDeviceClass.PRESSURE, 0),
        (UnitOfPressure.PA, SensorDeviceClass.PRESSURE, 0),
        ("µmol/m²/s", None, 0),
        ("mol/m²/d", None, 1),
        (DEGREE, None, 0),
        (UnitOfPower.WATT, SensorDeviceClass.POWER, 0),
        (UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, 2),
        (UnitOfMass.KILOGRAMS, SensorDeviceClass.WEIGHT, 1),
        (UnitOfMass.GRAMS, SensorDeviceClass.WEIGHT, 0),
    )
} | {
    # pH is dimensionless (a logarithmic ratio), so SensorDeviceClass.PH takes no unit.
    "pH": SensorEntityDescription(
        key="pH", device_class=SensorDeviceClass.PH, suggested_display_precision=1
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HortimaxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one sensor per readout, adding new ones as they appear."""
    coordinator = entry.runtime_data
    known: set[tuple[str, str]] = set()

    @callback
    def _add_new_entities() -> None:
        new_entities: list[HortimaxReadoutSensor] = []
        for device_id, device_data in coordinator.data.items():
            for key in device_data.readouts:
                if (device_id, key) in known:
                    continue
                known.add((device_id, key))
                new_entities.append(HortimaxReadoutSensor(coordinator, device_id, key))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


def _describe(readout: Readout) -> SensorEntityDescription:
    """Derive the description of the sensor for a readout.

    A device class is only assigned to a mapped unit: Home Assistant rejects
    values whose unit does not match the class. Dimensionless readouts are
    status codes, so they get no state class and integer display.
    """
    key = readout.identifier
    if readout.value_type is not ReadoutValueType.DOUBLE:
        return SensorEntityDescription(key=key)

    subject = readout_subject(readout.identifier)
    if subject in TIME_OF_DAY_READOUTS:
        return SensorEntityDescription(
            key=key, device_class=SensorDeviceClass.TIMESTAMP
        )
    # MEASUREMENT_ANGLE gives statistics the circular mean.
    if subject == WIND_DIRECTION_SUBJECT:
        return SensorEntityDescription(
            key=key,
            native_unit_of_measurement=DEGREE,
            device_class=SensorDeviceClass.WIND_DIRECTION,
            state_class=SensorStateClass.MEASUREMENT_ANGLE,
        )

    raw_unit = readout.unit
    if not raw_unit or raw_unit in DIMENSIONLESS_UNITS:
        return SensorEntityDescription(key=key, suggested_display_precision=0)

    unit = UNIT_MAP.get(raw_unit)
    if unit is None:
        # Truthful, but rules out a device class and any basis for a precision.
        return SensorEntityDescription(
            key=key,
            native_unit_of_measurement=raw_unit,
            state_class=SensorStateClass.MEASUREMENT,
        )

    description = UNIT_DESCRIPTIONS[unit]
    identifier = readout.identifier.lower()
    device_class = description.device_class
    if device_class is None:
        if unit == "%" and "relativehumidity" in identifier:
            device_class = SensorDeviceClass.HUMIDITY
        elif unit == UnitOfRatio.PARTS_PER_MILLION and (
            "co2" in identifier or "carbondioxide" in identifier
        ):
            # ppm is a generic concentration; only claim CO2 when the
            # readout says so, since growers define their own.
            device_class = SensorDeviceClass.CO2
        elif unit == UnitOfSpeed.METERS_PER_SECOND:
            device_class = (
                SensorDeviceClass.WIND_SPEED
                if "wind" in identifier
                else SensorDeviceClass.SPEED
            )
        elif unit == UnitOfVolume.CUBIC_METERS and readout.source.type == "GasMeter":
            device_class = SensorDeviceClass.GAS

    state_class: SensorStateClass | None
    if device_class in (SensorDeviceClass.ENERGY, SensorDeviceClass.GAS):
        # Core rejects MEASUREMENT for these. Daily counters reset at midnight,
        # which TOTAL_INCREASING handles and the energy dashboard needs; any
        # other meter readout has unknown cumulative semantics.
        state_class = (
            SensorStateClass.TOTAL_INCREASING
            if "consumptiontoday" in identifier
            else None
        )
    else:
        state_class = SensorStateClass.MEASUREMENT

    return replace(
        description, key=key, device_class=device_class, state_class=state_class
    )


class HortimaxReadoutSensor(HortimaxEntity, SensorEntity):
    """A single readout (measurement) from a HortOS source."""

    def __init__(
        self, coordinator: HortimaxCoordinator, device_id: str, key: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, key)
        readout = coordinator.data[device_id].readouts[key]
        self._attr_name = readout_display_name(readout.identifier)
        self._attr_icon = READOUT_ICONS.get(readout_subject(readout.identifier))
        # Settings are diagnostics, so measurements stand out on the device.
        if readout.identifier.lower().endswith("-actualsetting"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self.entity_description = _describe(readout)

        # A controller reports hundreds of unclassifiable status codes, so
        # those start disabled. A state class means a real measurement, which
        # stays enabled even without a device class for its unit.
        if (
            self.entity_description.device_class is None
            and self._attr_icon is None
            and self.entity_description.state_class is None
        ):
            self._attr_entity_registry_enabled_default = False

    @property
    @override
    def native_value(self) -> float | str | datetime | None:
        """Return the value of the readout."""
        if (readout := self.readout) is None or readout.value is None:
            return None
        if readout.value_type is not ReadoutValueType.DOUBLE:
            return str(readout.value)
        try:
            number = float(readout.value)
        except TypeError, ValueError:
            return None
        # float() and the JSON parser both accept NaN and Infinity, which
        # numeric sensors reject and timedelta() cannot convert.
        if not isfinite(number):
            return None
        subject = readout_subject(readout.identifier)
        if subject in TIME_OF_DAY_READOUTS:
            # Seconds since midnight at the controller. HortOS reports no
            # timezone, so this assumes it shares Home Assistant's. Anything
            # outside the day is not a time of day, and would either land on
            # another date or overflow timedelta().
            if not 0 <= number < SECONDS_PER_DAY:
                return None
            return dt_util.start_of_local_day() + timedelta(seconds=number)
        if subject == WIND_DIRECTION_SUBJECT:
            # Returns None for ids outside the known enumeration block.
            return decode_cardinal_wind_direction(number)
        return number
