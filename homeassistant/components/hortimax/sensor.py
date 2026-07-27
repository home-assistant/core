"""Sensor platform: one sensor per HortOS readout."""

from datetime import datetime, timedelta
from math import isfinite
from typing import override

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
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    EntityCategory,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DIMENSIONLESS_UNITS,
    READOUT_ICONS,
    TIME_OF_DAY_READOUTS,
    UNIT_DEVICE_CLASS,
    UNIT_MAP,
    UNIT_PRECISION,
    WIND_DIRECTION_SUBJECT,
)
from .coordinator import HortimaxConfigEntry, HortimaxCoordinator
from .entity import HortimaxEntity

PARALLEL_UPDATES = 0


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


def _describe(
    readout: Readout,
) -> tuple[str | None, SensorDeviceClass | None, SensorStateClass | None, int | None]:
    """Derive (unit, device class, state class, display precision).

    A device class is only assigned to a mapped unit: Home Assistant rejects
    values whose unit does not match the class. Dimensionless readouts are
    status codes, so they get no state class and integer display.
    """
    if readout.value_type is not ReadoutValueType.DOUBLE:
        return None, None, None, None

    subject = readout_subject(readout.identifier)
    if subject in TIME_OF_DAY_READOUTS:
        return None, SensorDeviceClass.TIMESTAMP, None, None
    # MEASUREMENT_ANGLE gives statistics the circular mean.
    if subject == WIND_DIRECTION_SUBJECT:
        return (
            DEGREE,
            SensorDeviceClass.WIND_DIRECTION,
            SensorStateClass.MEASUREMENT_ANGLE,
            None,
        )

    raw_unit = readout.unit
    if not raw_unit or raw_unit in DIMENSIONLESS_UNITS:
        return None, None, None, 0

    unit = UNIT_MAP.get(raw_unit)
    mapped = unit is not None
    if unit is None:
        unit = raw_unit  # truthful, but rules out a device class
    # An unmapped unit gives no basis for choosing a precision.
    precision = UNIT_PRECISION.get(unit) if mapped else None

    identifier = readout.identifier.lower()
    device_class: SensorDeviceClass | None = None
    if mapped:
        device_class = UNIT_DEVICE_CLASS.get(unit)
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
            elif (
                unit == UnitOfVolume.CUBIC_METERS and readout.source.type == "GasMeter"
            ):
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

    return unit, device_class, state_class, precision


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

        (
            self._attr_native_unit_of_measurement,
            self._attr_device_class,
            self._attr_state_class,
            self._attr_suggested_display_precision,
        ) = _describe(readout)

        # A controller reports hundreds of unclassifiable status codes, so
        # those start disabled. A state class means a real measurement, which
        # stays enabled even without a device class for its unit.
        if (
            self._attr_device_class is None
            and self._attr_icon is None
            and self._attr_state_class is None
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
            # timezone, so this assumes it shares Home Assistant's.
            return dt_util.start_of_local_day() + timedelta(seconds=number)
        if subject == WIND_DIRECTION_SUBJECT:
            # Returns None for ids outside the known enumeration block.
            return decode_cardinal_wind_direction(number)
        return number
