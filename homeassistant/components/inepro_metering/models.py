"""Home Assistant integration view of the shared Inepro Metering models."""

from dataclasses import replace

from inepro_metering.const import (
    FAMILY_LABELS,
    TRANSPORT_LABELS,
    MeterFamily,
    TransportType,
)
from inepro_metering.models import (
    GROW_ERROR_BIT_MESSAGES,
    MeterProfile,
    MeterSensorDescription,
    RegisterFormatType,
    RegisterType,
    RegisterValueType,
    decode_grow_error_code,
    format_grow_error_summary,
    get_profile as _package_get_profile,
    get_profile_for_variant as _package_get_profile_for_variant,
    get_profiles_for_family as _package_get_profiles_for_family,
    get_supported_families as _package_get_supported_families,
)

_ALL_GROW_MODELS = frozenset({"701", "750", "800", "850"})
_THREE_PHASE_GROW_MODELS = frozenset({"701", "750"})
_TARIFF_OPTIONS = {
    1: "T1",
    2: "T2",
    3: "T3",
    4: "T4",
}


def _count_for(value_type: RegisterValueType) -> int:
    """Return the number of Modbus registers for a value type."""
    if value_type in {
        RegisterValueType.UINT16,
        RegisterValueType.INT16,
        RegisterValueType.BCD16,
        RegisterValueType.HEX16,
    }:
        return 1
    return 2


def _energy_sensor(
    *,
    key: str,
    name: str,
    address: int,
    value_type: RegisterValueType,
    supported_models: frozenset[str],
    unit: str,
    register_unit: str,
    state_class: str = "total_increasing",
    device_class: str | None = None,
    enabled_by_default: bool = False,
    entity_category: str | None = None,
) -> MeterSensorDescription:
    """Build one GROW energy register description."""
    return MeterSensorDescription(
        key=key,
        name=name,
        register_type=RegisterType.HOLDING,
        address=address,
        count=_count_for(value_type),
        value_type=value_type,
        scale=0.001,
        supported_models=supported_models,
        native_unit_of_measurement=unit,
        device_class=device_class,
        state_class=state_class,
        suggested_display_precision=3,
        entity_registry_enabled_default=enabled_by_default,
        entity_category=entity_category,
        register_unit=register_unit,
        register_format=RegisterFormatType.DEC,
    )


def _active_energy_sensor(
    *,
    key: str,
    name: str,
    address: int,
    value_type: RegisterValueType,
    supported_models: frozenset[str] = _ALL_GROW_MODELS,
    state_class: str = "total_increasing",
    enabled_by_default: bool = False,
) -> MeterSensorDescription:
    """Build one active-energy register description."""
    return _energy_sensor(
        key=key,
        name=name,
        address=address,
        value_type=value_type,
        supported_models=supported_models,
        unit="kWh",
        register_unit="Wh",
        state_class=state_class,
        device_class="energy",
        enabled_by_default=enabled_by_default,
    )


def _reactive_energy_sensor(
    *,
    key: str,
    name: str,
    address: int,
    value_type: RegisterValueType,
    supported_models: frozenset[str] = _ALL_GROW_MODELS,
) -> MeterSensorDescription:
    """Build one disabled-by-default reactive-energy register description."""
    return _energy_sensor(
        key=key,
        name=name,
        address=address,
        value_type=value_type,
        supported_models=supported_models,
        unit="kvarh",
        register_unit="varh",
    )


def _apparent_energy_sensor(
    *,
    key: str,
    name: str,
    address: int,
    value_type: RegisterValueType,
    supported_models: frozenset[str] = _ALL_GROW_MODELS,
) -> MeterSensorDescription:
    """Build one disabled-by-default apparent-energy register description."""
    return _energy_sensor(
        key=key,
        name=name,
        address=address,
        value_type=value_type,
        supported_models=supported_models,
        unit="kVAh",
        register_unit="VAh",
    )


def _resettable_energy_sensor(
    *,
    key: str,
    name: str,
    address: int,
    supported_models: frozenset[str] = _ALL_GROW_MODELS,
) -> MeterSensorDescription:
    """Build one disabled diagnostic resettable energy counter."""
    return _energy_sensor(
        key=key,
        name=name,
        address=address,
        value_type=RegisterValueType.INT32,
        supported_models=supported_models,
        unit="kWh",
        register_unit="Wh",
        state_class="total",
        device_class="energy",
        entity_category="diagnostic",
    )


_GROW_EXTRA_MEASUREMENT_SENSORS: tuple[MeterSensorDescription, ...] = (
    _active_energy_sensor(
        key="active_energy_total",
        name="Active Energy Total",
        address=0x6000,
        value_type=RegisterValueType.INT32,
        state_class="total",
    ),
    _active_energy_sensor(
        key="active_energy_t1",
        name="Active Energy T1",
        address=0x6002,
        value_type=RegisterValueType.INT32,
    ),
    _active_energy_sensor(
        key="active_energy_t2",
        name="Active Energy T2",
        address=0x6004,
        value_type=RegisterValueType.INT32,
    ),
    _active_energy_sensor(
        key="active_energy_l1",
        name="Active Energy L1",
        address=0x6006,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        state_class="total",
    ),
    _active_energy_sensor(
        key="active_energy_l2",
        name="Active Energy L2",
        address=0x6008,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        state_class="total",
    ),
    _active_energy_sensor(
        key="active_energy_l3",
        name="Active Energy L3",
        address=0x600A,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        state_class="total",
    ),
    _active_energy_sensor(
        key="active_energy_import_total",
        name="Active Energy Import Total",
        address=0x600C,
        value_type=RegisterValueType.UINT32,
        enabled_by_default=True,
    ),
    _active_energy_sensor(
        key="active_energy_import_t1",
        name="Active Energy Import T1",
        address=0x600E,
        value_type=RegisterValueType.UINT32,
    ),
    _active_energy_sensor(
        key="active_energy_import_t2",
        name="Active Energy Import T2",
        address=0x6010,
        value_type=RegisterValueType.UINT32,
    ),
    _active_energy_sensor(
        key="active_energy_import_l1",
        name="Active Energy Import L1",
        address=0x6012,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        enabled_by_default=True,
    ),
    _active_energy_sensor(
        key="active_energy_import_l2",
        name="Active Energy Import L2",
        address=0x6014,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        enabled_by_default=True,
    ),
    _active_energy_sensor(
        key="active_energy_import_l3",
        name="Active Energy Import L3",
        address=0x6016,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        enabled_by_default=True,
    ),
    _active_energy_sensor(
        key="active_energy_export_total",
        name="Active Energy Export Total",
        address=0x6018,
        value_type=RegisterValueType.UINT32,
        enabled_by_default=True,
    ),
    _active_energy_sensor(
        key="active_energy_export_t1",
        name="Active Energy Export T1",
        address=0x601A,
        value_type=RegisterValueType.UINT32,
    ),
    _active_energy_sensor(
        key="active_energy_export_t2",
        name="Active Energy Export T2",
        address=0x601C,
        value_type=RegisterValueType.UINT32,
    ),
    _active_energy_sensor(
        key="active_energy_export_l1",
        name="Active Energy Export L1",
        address=0x601E,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        enabled_by_default=True,
    ),
    _active_energy_sensor(
        key="active_energy_export_l2",
        name="Active Energy Export L2",
        address=0x6020,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        enabled_by_default=True,
    ),
    _active_energy_sensor(
        key="active_energy_export_l3",
        name="Active Energy Export L3",
        address=0x6022,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
        enabled_by_default=True,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_total",
        name="Reactive Energy Total",
        address=0x6024,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_t1",
        name="Reactive Energy T1",
        address=0x6026,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_t2",
        name="Reactive Energy T2",
        address=0x6028,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_l1",
        name="Reactive Energy L1",
        address=0x602A,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_l2",
        name="Reactive Energy L2",
        address=0x602C,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_l3",
        name="Reactive Energy L3",
        address=0x602E,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_import_total",
        name="Reactive Energy Import Total",
        address=0x6030,
        value_type=RegisterValueType.UINT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_import_t1",
        name="Reactive Energy Import T1",
        address=0x6032,
        value_type=RegisterValueType.UINT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_import_t2",
        name="Reactive Energy Import T2",
        address=0x6034,
        value_type=RegisterValueType.UINT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_import_l1",
        name="Reactive Energy Import L1",
        address=0x6036,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_import_l2",
        name="Reactive Energy Import L2",
        address=0x6038,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_import_l3",
        name="Reactive Energy Import L3",
        address=0x603A,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_export_total",
        name="Reactive Energy Export Total",
        address=0x603C,
        value_type=RegisterValueType.UINT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_export_t1",
        name="Reactive Energy Export T1",
        address=0x603E,
        value_type=RegisterValueType.UINT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_export_t2",
        name="Reactive Energy Export T2",
        address=0x6040,
        value_type=RegisterValueType.UINT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_export_l1",
        name="Reactive Energy Export L1",
        address=0x6042,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_export_l2",
        name="Reactive Energy Export L2",
        address=0x6044,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_export_l3",
        name="Reactive Energy Export L3",
        address=0x6046,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _resettable_energy_sensor(
        key="resettable_day_counter_total",
        name="Resettable Day Counter Total",
        address=0x6049,
    ),
    _active_energy_sensor(
        key="active_energy_t3",
        name="Active Energy T3",
        address=0x604B,
        value_type=RegisterValueType.INT32,
    ),
    _active_energy_sensor(
        key="active_energy_t4",
        name="Active Energy T4",
        address=0x604D,
        value_type=RegisterValueType.INT32,
    ),
    _active_energy_sensor(
        key="active_energy_import_t3",
        name="Active Energy Import T3",
        address=0x604F,
        value_type=RegisterValueType.INT32,
    ),
    _active_energy_sensor(
        key="active_energy_import_t4",
        name="Active Energy Import T4",
        address=0x6051,
        value_type=RegisterValueType.INT32,
    ),
    _active_energy_sensor(
        key="active_energy_export_t3",
        name="Active Energy Export T3",
        address=0x6053,
        value_type=RegisterValueType.INT32,
    ),
    _active_energy_sensor(
        key="active_energy_export_t4",
        name="Active Energy Export T4",
        address=0x6055,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_t3",
        name="Reactive Energy T3",
        address=0x6057,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_t4",
        name="Reactive Energy T4",
        address=0x6059,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_import_t3",
        name="Reactive Energy Import T3",
        address=0x605B,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_import_t4",
        name="Reactive Energy Import T4",
        address=0x605D,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_export_t3",
        name="Reactive Energy Export T3",
        address=0x605F,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_export_t4",
        name="Reactive Energy Export T4",
        address=0x6061,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q1_total",
        name="Reactive Energy Q1 Total",
        address=0x6063,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q1_t1",
        name="Reactive Energy Q1 T1",
        address=0x6065,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q1_t2",
        name="Reactive Energy Q1 T2",
        address=0x6067,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q1_t3",
        name="Reactive Energy Q1 T3",
        address=0x6069,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q1_t4",
        name="Reactive Energy Q1 T4",
        address=0x606B,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q2_total",
        name="Reactive Energy Q2 Total",
        address=0x606D,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q2_t1",
        name="Reactive Energy Q2 T1",
        address=0x606F,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q2_t2",
        name="Reactive Energy Q2 T2",
        address=0x6071,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q2_t3",
        name="Reactive Energy Q2 T3",
        address=0x6073,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q2_t4",
        name="Reactive Energy Q2 T4",
        address=0x6075,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q3_total",
        name="Reactive Energy Q3 Total",
        address=0x6077,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q3_t1",
        name="Reactive Energy Q3 T1",
        address=0x6079,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q3_t2",
        name="Reactive Energy Q3 T2",
        address=0x607B,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q3_t3",
        name="Reactive Energy Q3 T3",
        address=0x607D,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q3_t4",
        name="Reactive Energy Q3 T4",
        address=0x607F,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q4_total",
        name="Reactive Energy Q4 Total",
        address=0x6081,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q4_t1",
        name="Reactive Energy Q4 T1",
        address=0x6083,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q4_t2",
        name="Reactive Energy Q4 T2",
        address=0x6085,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q4_t3",
        name="Reactive Energy Q4 T3",
        address=0x6087,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q4_t4",
        name="Reactive Energy Q4 T4",
        address=0x6089,
        value_type=RegisterValueType.INT32,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q1_l1",
        name="Reactive Energy Q1 L1",
        address=0x6091,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q1_l2",
        name="Reactive Energy Q1 L2",
        address=0x6093,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q1_l3",
        name="Reactive Energy Q1 L3",
        address=0x6095,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q2_l1",
        name="Reactive Energy Q2 L1",
        address=0x6097,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q2_l2",
        name="Reactive Energy Q2 L2",
        address=0x6099,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q2_l3",
        name="Reactive Energy Q2 L3",
        address=0x609B,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q3_l1",
        name="Reactive Energy Q3 L1",
        address=0x609D,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q3_l2",
        name="Reactive Energy Q3 L2",
        address=0x609F,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q3_l3",
        name="Reactive Energy Q3 L3",
        address=0x60A1,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q4_l1",
        name="Reactive Energy Q4 L1",
        address=0x60A3,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q4_l2",
        name="Reactive Energy Q4 L2",
        address=0x60A5,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _reactive_energy_sensor(
        key="reactive_energy_q4_l3",
        name="Reactive Energy Q4 L3",
        address=0x60A7,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _resettable_energy_sensor(
        key="resettable_day_counter_l1",
        name="Resettable Day Counter L1",
        address=0x60AB,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _resettable_energy_sensor(
        key="resettable_day_counter_l2",
        name="Resettable Day Counter L2",
        address=0x60AD,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _resettable_energy_sensor(
        key="resettable_day_counter_l3",
        name="Resettable Day Counter L3",
        address=0x60AF,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_total",
        name="Apparent Energy Total",
        address=0x60B9,
        value_type=RegisterValueType.INT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_t1",
        name="Apparent Energy T1",
        address=0x60BB,
        value_type=RegisterValueType.INT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_t2",
        name="Apparent Energy T2",
        address=0x60BD,
        value_type=RegisterValueType.INT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_l1",
        name="Apparent Energy L1",
        address=0x60BF,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_l2",
        name="Apparent Energy L2",
        address=0x6101,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_l3",
        name="Apparent Energy L3",
        address=0x6103,
        value_type=RegisterValueType.INT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_import_total",
        name="Apparent Energy Import Total",
        address=0x6105,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_import_t1",
        name="Apparent Energy Import T1",
        address=0x6107,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_import_t2",
        name="Apparent Energy Import T2",
        address=0x6109,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_import_l1",
        name="Apparent Energy Import L1",
        address=0x610B,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_import_l2",
        name="Apparent Energy Import L2",
        address=0x610D,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_import_l3",
        name="Apparent Energy Import L3",
        address=0x610F,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_export_total",
        name="Apparent Energy Export Total",
        address=0x6111,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_export_t1",
        name="Apparent Energy Export T1",
        address=0x6113,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_export_t2",
        name="Apparent Energy Export T2",
        address=0x6115,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_export_l1",
        name="Apparent Energy Export L1",
        address=0x6117,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_export_l2",
        name="Apparent Energy Export L2",
        address=0x6119,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_export_l3",
        name="Apparent Energy Export L3",
        address=0x611B,
        value_type=RegisterValueType.UINT32,
        supported_models=_THREE_PHASE_GROW_MODELS,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_t3",
        name="Apparent Energy T3",
        address=0x611D,
        value_type=RegisterValueType.INT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_t4",
        name="Apparent Energy T4",
        address=0x611F,
        value_type=RegisterValueType.INT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_import_t3",
        name="Apparent Energy Import T3",
        address=0x6121,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_import_t4",
        name="Apparent Energy Import T4",
        address=0x6123,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_export_t3",
        name="Apparent Energy Export T3",
        address=0x6125,
        value_type=RegisterValueType.UINT32,
    ),
    _apparent_energy_sensor(
        key="apparent_energy_export_t4",
        name="Apparent Energy Export T4",
        address=0x6127,
        value_type=RegisterValueType.UINT32,
    ),
    _resettable_energy_sensor(
        key="previous_resettable_day_counter",
        name="Previous Resettable Day Counter",
        address=0x6200,
    ),
)

_GROW_EXTRA_DIAGNOSTIC_SENSORS: tuple[MeterSensorDescription, ...] = (
    MeterSensorDescription(
        key="active_tariff",
        name="Active Tariff",
        register_type=RegisterType.HOLDING,
        address=0x6048,
        count=1,
        value_type=RegisterValueType.UINT16,
        supported_models=_ALL_GROW_MODELS,
        state_class=None,
        entity_category="diagnostic",
        options=_TARIFF_OPTIONS,
        register_format=RegisterFormatType.ENUM,
    ),
)


def _supported_extra_sensors(
    sensors: tuple[MeterSensorDescription, ...],
    model_code: str,
    existing_keys: set[str],
) -> tuple[MeterSensorDescription, ...]:
    """Return extra sensors supported by one GROW model."""
    return tuple(
        sensor
        for sensor in sensors
        if model_code in sensor.supported_models and sensor.key not in existing_keys
    )


def _augment_grow_profile(profile: MeterProfile) -> MeterProfile:
    """Add Core PR GROW energy register coverage on top of the package profile."""
    if profile.family is not MeterFamily.GROW:
        return profile

    existing_measurement_keys = {sensor.key for sensor in profile.measurement_sensors}
    existing_diagnostic_keys = {sensor.key for sensor in profile.diagnostic_sensors}
    extra_measurements = _supported_extra_sensors(
        _GROW_EXTRA_MEASUREMENT_SENSORS,
        profile.model_code,
        existing_measurement_keys,
    )
    extra_diagnostics = _supported_extra_sensors(
        _GROW_EXTRA_DIAGNOSTIC_SENSORS,
        profile.model_code,
        existing_diagnostic_keys,
    )

    if not extra_measurements and not extra_diagnostics:
        return profile

    return replace(
        profile,
        measurement_sensors=profile.measurement_sensors + extra_measurements,
        diagnostic_sensors=profile.diagnostic_sensors + extra_diagnostics,
    )


def get_profile(family: str | MeterFamily, variant: str) -> MeterProfile:
    """Return the configured profile."""
    return _augment_grow_profile(_package_get_profile(family, variant))


def get_profile_for_variant(variant: str) -> MeterProfile:
    """Return the configured profile for a globally unique variant key."""
    return _augment_grow_profile(_package_get_profile_for_variant(variant))


def get_profiles_for_family(family: str | MeterFamily) -> dict[str, MeterProfile]:
    """Return all profiles for a family."""
    return {
        variant: _augment_grow_profile(profile)
        for variant, profile in _package_get_profiles_for_family(family).items()
    }


def get_supported_families() -> tuple[MeterFamily, ...]:
    """Return families that currently expose at least one selectable profile."""
    return _package_get_supported_families()


__all__ = [
    "FAMILY_LABELS",
    "GROW_ERROR_BIT_MESSAGES",
    "TRANSPORT_LABELS",
    "MeterFamily",
    "MeterProfile",
    "MeterSensorDescription",
    "RegisterFormatType",
    "RegisterType",
    "RegisterValueType",
    "TransportType",
    "decode_grow_error_code",
    "format_grow_error_summary",
    "get_profile",
    "get_profile_for_variant",
    "get_profiles_for_family",
    "get_supported_families",
]
