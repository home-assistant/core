"""Sensor platform for the BLUETTI Modbus integration."""

from enum import Enum
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

PARALLEL_UPDATES = 0

# No physical unit, and no entity of their own yet: the fault/warning/status
# enums read here belong on a binary_sensor/sensor split, a follow-up PR to
# keep this one reviewable. Exposed here as diagnostics in the meantime.
_DIAGNOSTIC_FIELDS = frozenset(
    {
        "d_inverter_fault",
        "d_inverter_status",
        "d_inverter_warning",
        "d_inverter_type",
        "d_num_inverters",
        "d_num_battery_packs",
        "d_ver_arm",
        "d_ver_dsp",
        "b_cell_count",
        "b_cycle_count",
        "b_ntc_count",
        "b_type",
    }
)

# Exposed as DeviceInfo.serial_number (see entity.py) instead of a sensor -
# a serial number is device identity, not a measurement. Still read every
# poll, unlike EXCLUDED_FIELDS in const.py: the coordinator's own per-poll
# identity check (coordinator.py) depends on it.
_ENTITY_EXCLUDED_FIELDS = frozenset({"d_serial"})

# Lifetime counters. HA's own TOTAL_INCREASING handling covers an occasional
# drop as a meter reset; this integration does not additionally clamp or
# restore these values itself.
_TOTAL_ENERGY_FIELDS = frozenset(
    {
        "ac_o_e_total",
        "b_i_e",
        "b_o_e",
        "g_i_e_total",
        "g_o_e_total",
        "pv_ac_e",
        "pv_i_e_total",
    }
)

# The battery's present charge level - SoH percentages are health, not charge,
# and get no device class below.
_BATTERY_LEVEL_FIELDS = frozenset({"b_soc", "b_soc_total"})

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


def _describe(name: str, field: RegisterField[object]) -> SensorEntityDescription:
    """Build an entity description for one register field."""
    if (
        isinstance(field, NumberField)
        and isinstance(field.convert, type)
        and issubclass(field.convert, Enum)
    ):
        return SensorEntityDescription(
            key=name,
            translation_key=name,
            device_class=SensorDeviceClass.ENUM,
            options=[_slug(member.name) for member in field.convert],
            entity_category=EntityCategory.DIAGNOSTIC
            if name in _DIAGNOSTIC_FIELDS
            else None,
        )

    if name in _TOTAL_ENERGY_FIELDS:
        return SensorEntityDescription(
            key=name,
            translation_key=name,
            native_unit_of_measurement=field.unit,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        )

    if name in _BATTERY_LEVEL_FIELDS:
        return SensorEntityDescription(
            key=name,
            translation_key=name,
            native_unit_of_measurement=field.unit,
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
        )

    device_class = _UNIT_DEVICE_CLASSES.get(field.unit or "")

    return SensorEntityDescription(
        key=name,
        translation_key=name,
        native_unit_of_measurement=field.unit,
        device_class=device_class,
        state_class=SensorStateClass.MEASUREMENT if device_class else None,
        entity_category=EntityCategory.DIAGNOSTIC
        if name in _DIAGNOSTIC_FIELDS
        else None,
    )


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
        translated to its stable state slug here rather than exposing the
        library's own repr.
        """
        value = self.coordinator.device.values.get(self._field_name)
        if isinstance(value, Enum):
            return _slug(value.name)
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
