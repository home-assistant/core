"""Sensor platform: one sensor per HortOS readout."""

from datetime import datetime, timedelta
from typing import override

from aiohortos import Readout, ReadoutValueType, decode_cardinal_wind_direction

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import DEGREE, EntityCategory, UnitOfSpeed, UnitOfVolume
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
from .naming import readout_display_name, readout_subject

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
        async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


def _describe(
    readout: Readout,
) -> tuple[str | None, SensorDeviceClass | None, SensorStateClass | None, int | None]:
    """Derive (unit, device class, state class, display precision).

    Device classes are only assigned for units mapped to a Home Assistant
    unit; an unmapped raw unit with a device class would make Home Assistant
    reject the value. Dimensionless readouts (Scalar) are status/override
    codes, which would pollute long-term statistics, so they get no state
    class - and integer display, as their values are codes like 6561.
    """
    if readout.value_type is not ReadoutValueType.DOUBLE:
        return None, None, None, None

    subject = readout_subject(readout.identifier)
    # Seconds-since-midnight readouts are surfaced as timestamps;
    # native_value turns the second count into today's datetime.
    if subject in TIME_OF_DAY_READOUTS:
        return None, SensorDeviceClass.TIMESTAMP, None, None
    # CardinalWindDirection is an enum code; native_value turns it into a
    # bearing in degrees (statistics use the circular mean for this class).
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
        unit = raw_unit  # truthful fallback, but no device class
    precision = UNIT_PRECISION.get(unit, 0) if mapped else 0

    identifier = readout.identifier.lower()
    device_class: SensorDeviceClass | None = None
    if mapped:
        device_class = UNIT_DEVICE_CLASS.get(unit)
        if device_class is None:
            if unit == "%" and "relativehumidity" in identifier:
                device_class = SensorDeviceClass.HUMIDITY
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

    # Daily consumption counters (electricity/gas meters) reset at midnight,
    # which TOTAL_INCREASING handles; this also feeds the energy dashboard.
    if "consumptiontoday" in identifier and device_class in (
        SensorDeviceClass.ENERGY,
        SensorDeviceClass.GAS,
    ):
        state_class = SensorStateClass.TOTAL_INCREASING
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
        # Static settings readouts go to the diagnostic section so the actual
        # measurements stand out on the device page.
        if readout.identifier.lower().endswith("-actualsetting"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        (
            self._attr_native_unit_of_measurement,
            self._attr_device_class,
            self._attr_state_class,
            self._attr_suggested_display_precision,
        ) = _describe(readout)

        # Readouts that could not be classified at all are obscure status and
        # override codes: a controller reports hundreds of them, so they are
        # created disabled and can be enabled per readout. A readout with a
        # state class is a real measurement and stays enabled even when
        # Home Assistant has no device class for its unit (vent and screen
        # positions, irrigation volumes, radiation sums).
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
        subject = readout_subject(readout.identifier)
        if subject in TIME_OF_DAY_READOUTS:
            # Seconds since local midnight -> today's timestamp.
            return dt_util.start_of_local_day() + timedelta(seconds=number)
        if subject == WIND_DIRECTION_SUBJECT:
            # An enumeration member id, not a bearing; the library owns that
            # table and returns None for anything outside it.
            return decode_cardinal_wind_direction(readout.value)
        return number
