"""Sensor platform for the BLUETTI Modbus integration."""

from typing import cast, override

from modbus_connection.model import RegisterField

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import BluettiModbusConfigEntry
from .entity import BluettiModbusEntity

PARALLEL_UPDATES = 0

# No physical unit, and no entity of their own yet: the fault/warning/status
# bits and the on/off switches read here belong on binary_sensor/switch
# platforms, each its own follow-up PR to keep this one reviewable. Exposed
# here as read-only diagnostics in the meantime, not left out entirely.
_DIAGNOSTIC_FIELDS = frozenset(
    {
        "ac_o_switch",
        "g_i_switch",
        "g_o_switch",
        "d_inverter_fault",
        "d_inverter_status",
        "d_inverter_warning",
        "d_inverter_type",
        "d_num_inverters",
        "d_num_battery_packs",
        "b_cell_count",
        "b_cycle_count",
        "b_ntc_count",
        "b_soc_high",
        "b_soc_low",
        "b_type",
    }
)

# Lifetime counters: hold the highest value the device has reported.
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


def _describe(name: str, field: RegisterField[object]) -> SensorEntityDescription:
    """Build an entity description for one register field."""
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
        """Return the field's most recently read value."""
        return cast(StateType, self.coordinator.device.values.get(self._field_name))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluettiModbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BLUETTI Modbus sensors from a config entry."""
    device = entry.runtime_data.coordinator.device
    async_add_entities(
        BluettiModbusSensor(entry=entry, description=_describe(name, field))
        for name in device.field_names()
        if (field := device.get_field(name)) is not None
    )
