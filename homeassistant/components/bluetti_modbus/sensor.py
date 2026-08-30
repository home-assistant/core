"""Sensor platform for the BLUETTI Modbus integration."""

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import re
from typing import cast, override

from bluetti_modbus_lib.base_devices.bluetti_device import BluettiDevice
from modbus_connection.model import RegisterField
from modbus_connection.model.fields import NumberField

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import BluettiModbusConfigEntry
from .entity import BluettiModbusEntity

# Exposed as DeviceInfo instead of a sensor - device identity/metadata, not a
# measurement. Still read every poll, unlike EXCLUDED_FIELDS in const.py:
# d_serial feeds the coordinator's own per-poll identity check
# (coordinator.py), and the firmware fields are read at the same first
# refresh __init__.py already builds DeviceInfo.sw_version from.
_ENTITY_EXCLUDED_FIELDS = frozenset({"d_serial", "d_ver_arm", "d_ver_dsp"})


@dataclass(frozen=True, kw_only=True)
class _FieldOverride:
    """One field's overrides.

    What its entity needs beyond what bluetti-modbus-lib's own field
    metadata (unit, whether it's an enum) already says - one object per
    field, instead of separate membership sets for each concern.
    """

    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    entity_category: EntityCategory | None = None


_DIAGNOSTIC = _FieldOverride(entity_category=EntityCategory.DIAGNOSTIC)
# HA's own TOTAL_INCREASING handling covers an occasional drop as a meter
# reset; this integration does not additionally clamp or restore these
# values itself.
_LIFETIME_ENERGY = _FieldOverride(
    device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING
)
# The battery's present charge level - SoH percentages are health, not
# charge, and use the default (unit-derived) device class instead.
_BATTERY_LEVEL = _FieldOverride(
    device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT
)

_FIELD_OVERRIDES: dict[str, _FieldOverride] = {
    # Fields without a physical unit that currently belong on the sensor
    # platform are exposed as diagnostics. Fault and warning fields remain
    # excluded entirely (see EXCLUDED_FIELDS in const.py) until their
    # bitmaps can be represented as binary sensors.
    "d_inverter_status": _DIAGNOSTIC,
    "d_inverter_type": _DIAGNOSTIC,
    "d_num_inverters": _DIAGNOSTIC,
    "d_num_battery_packs": _DIAGNOSTIC,
    "b_cell_count": _DIAGNOSTIC,
    "b_cycle_count": _DIAGNOSTIC,
    "b_ntc_count": _DIAGNOSTIC,
    "b_type": _DIAGNOSTIC,
    "ac_o_e_total": _LIFETIME_ENERGY,
    "b_i_e": _LIFETIME_ENERGY,
    "b_o_e": _LIFETIME_ENERGY,
    "g_i_e_total": _LIFETIME_ENERGY,
    "g_o_e_total": _LIFETIME_ENERGY,
    "pv_ac_e": _LIFETIME_ENERGY,
    "pv_i_e_total": _LIFETIME_ENERGY,
    "b_soc": _BATTERY_LEVEL,
    "b_soc_total": _BATTERY_LEVEL,
}

# Anything not in _FIELD_OVERRIDES above falls back to this, keyed by the
# field's own unit (also bluetti-modbus-lib's own metadata, not guessed) -
# there is no per-field override to state, only a per-unit default.
_UNIT_DEVICE_CLASSES: dict[str, SensorDeviceClass] = {
    "V": SensorDeviceClass.VOLTAGE,
    "A": SensorDeviceClass.CURRENT,
    "W": SensorDeviceClass.POWER,
    "Hz": SensorDeviceClass.FREQUENCY,
    "°C": SensorDeviceClass.TEMPERATURE,
}


def _slug(name: str) -> str:
    """Turn an UpperCamelCase enum member name into a snake_case state slug."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


@lru_cache
def _enum_value_map(enum_cls: type[Enum]) -> dict[Enum, str]:
    """Return a member -> state slug lookup, built once per enum type.

    Cached rather than recomputed on every poll: the transform itself only
    needs to run once per enum type (here, at most a handful of member
    counts to look through), not once per entity per refresh.
    """
    return {member: _slug(member.name) for member in enum_cls}


def _describe(name: str, field: RegisterField[object]) -> SensorEntityDescription:
    """Build an entity description for one register field.

    Combines bluetti-modbus-lib's own field metadata (unit, whether it's an
    enum) with this integration's per-field override, if any - one lookup,
    not several membership checks against separate sets.
    """
    field_override = _FIELD_OVERRIDES.get(name)

    if (
        isinstance(field, NumberField)
        and isinstance(field.convert, type)
        and issubclass(field.convert, Enum)
    ):
        return SensorEntityDescription(
            key=name,
            translation_key=name,
            device_class=SensorDeviceClass.ENUM,
            options=list(_enum_value_map(field.convert).values()),
            entity_category=field_override.entity_category if field_override else None,
        )

    if field_override is not None and field_override.device_class is not None:
        return SensorEntityDescription(
            key=name,
            translation_key=name,
            native_unit_of_measurement=field.unit,
            device_class=field_override.device_class,
            state_class=field_override.state_class,
        )

    device_class = _UNIT_DEVICE_CLASSES.get(field.unit or "")

    return SensorEntityDescription(
        key=name,
        translation_key=name,
        native_unit_of_measurement=field.unit,
        device_class=device_class,
        state_class=SensorStateClass.MEASUREMENT if device_class else None,
        entity_category=field_override.entity_category if field_override else None,
    )


# Entities only read from the coordinator and never poll or call the API
# themselves, so there is no need to limit concurrent updates.
PARALLEL_UPDATES = 0


class BluettiModbusSensor(BluettiModbusEntity, SensorEntity):
    """Defines a BLUETTI Modbus sensor."""

    def __init__(
        self, *, entry: BluettiModbusConfigEntry, description: SensorEntityDescription
    ) -> None:
        """Initialize a BLUETTI Modbus sensor."""
        super().__init__(entry=entry, field_name=description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the field's most recently read value.

        An enum-typed field decodes to an Enum member, not a plain value -
        translated to its stable state slug here (via the same lookup its
        entity description's options list was built from) rather than
        exposing the library's own repr.
        """
        value = self.coordinator.device.values.get(self._field_name)
        if isinstance(value, Enum):
            return _enum_value_map(type(value))[value]
        return cast(StateType, value)


def _describe_fields(device: BluettiDevice) -> list[SensorEntityDescription]:
    """Build entity descriptions for every field this device exposes as a sensor."""
    descriptions = []
    for name in device.field_names():
        if name in _ENTITY_EXCLUDED_FIELDS:
            continue
        field = device.get_field(name)
        assert field is not None  # every name from field_names() has one
        descriptions.append(_describe(name, field))
    return descriptions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluettiModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLUETTI Modbus sensors from a config entry."""
    device = entry.runtime_data.coordinator.device
    async_add_entities(
        BluettiModbusSensor(entry=entry, description=description)
        for description in _describe_fields(device)
    )
