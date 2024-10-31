"""Test Enphase Envoy sensors."""

from itertools import chain
import logging
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyenphase.const import PHASENAMES
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.enphase_envoy.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_eu_batt",
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor platform entities against snapshot."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


PRODUCTION_NAMES: tuple[str, ...] = (
    "current_power_production",
    "energy_production_today",
    "energy_production_last_seven_days",
    "lifetime_energy_production",
)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_eu_batt",
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_production_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test production entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    data = mock_envoy.data.system_production
    PRODUCTION_TARGETS: tuple[float, ...] = (
        data.watts_now / 1000.0,
        data.watt_hours_today / 1000.0,
        data.watt_hours_last_7_days / 1000.0,
        data.watt_hours_lifetime / 1000000.0,
    )

    for name, target in list(zip(PRODUCTION_NAMES, PRODUCTION_TARGETS, strict=False)):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target


PRODUCTION_PHASE_NAMES: list[str] = [
    f"{name}_{phase.lower()}" for phase in PHASENAMES for name in PRODUCTION_NAMES
]


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_production_phase_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test production phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    PRODUCTION_PHASE_TARGET = chain(
        *[
            (
                phase_data.watts_now / 1000.0,
                phase_data.watt_hours_today / 1000.0,
                phase_data.watt_hours_last_7_days / 1000.0,
                phase_data.watt_hours_lifetime / 1000000.0,
            )
            for phase_data in mock_envoy.data.system_production_phases.values()
        ]
    )

    for name, target in list(
        zip(PRODUCTION_PHASE_NAMES, PRODUCTION_PHASE_TARGET, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target


CONSUMPTION_NAMES: tuple[str, ...] = (
    "current_power_consumption",
    "energy_consumption_today",
    "energy_consumption_last_seven_days",
    "lifetime_energy_consumption",
)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_1p_metered",
        "envoy_eu_batt",
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_consumption_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test consumption entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    data = mock_envoy.data.system_consumption
    CONSUMPTION_TARGETS = (
        data.watts_now / 1000.0,
        data.watt_hours_today / 1000.0,
        data.watt_hours_last_7_days / 1000.0,
        data.watt_hours_lifetime / 1000000.0,
    )

    for name, target in list(zip(CONSUMPTION_NAMES, CONSUMPTION_TARGETS, strict=False)):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target


NET_CONSUMPTION_NAMES: tuple[str, ...] = (
    "balanced_net_power_consumption",
    "lifetime_balanced_net_energy_consumption",
)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_1p_metered",
        "envoy_eu_batt",
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_net_consumption_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test net consumption entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    data = mock_envoy.data.system_net_consumption
    NET_CONSUMPTION_TARGETS = (
        data.watts_now / 1000.0,
        data.watt_hours_lifetime / 1000.0,
    )
    for name, target in list(
        zip(NET_CONSUMPTION_NAMES, NET_CONSUMPTION_TARGETS, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target


CONSUMPTION_PHASE_NAMES: list[str] = [
    f"{name}_{phase.lower()}" for phase in PHASENAMES for name in CONSUMPTION_NAMES
]


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_consumption_phase_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test consumption phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    CONSUMPTION_PHASE_TARGET = chain(
        *[
            (
                phase_data.watts_now / 1000.0,
                phase_data.watt_hours_today / 1000.0,
                phase_data.watt_hours_last_7_days / 1000.0,
                phase_data.watt_hours_lifetime / 1000000.0,
            )
            for phase_data in mock_envoy.data.system_consumption_phases.values()
        ]
    )

    for name, target in list(
        zip(CONSUMPTION_PHASE_NAMES, CONSUMPTION_PHASE_TARGET, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target


NET_CONSUMPTION_PHASE_NAMES: list[str] = [
    f"{name}_{phase.lower()}" for phase in PHASENAMES for name in NET_CONSUMPTION_NAMES
]


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_net_consumption_phase_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test consumption phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    NET_CONSUMPTION_PHASE_TARGET = chain(
        *[
            (
                phase_data.watts_now / 1000.0,
                phase_data.watt_hours_lifetime / 1000.0,
            )
            for phase_data in mock_envoy.data.system_net_consumption_phases.values()
        ]
    )
    for name, target in list(
        zip(NET_CONSUMPTION_PHASE_NAMES, NET_CONSUMPTION_PHASE_TARGET, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target


CT_PRODUCTION_NAMES_INT = ("meter_status_flags_active_production_ct",)
CT_PRODUCTION_NAMES_STR = ("metering_status_production_ct",)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_production_ct_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
) -> None:
    """Test production CT phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    data = mock_envoy.data.ctmeter_production

    CT_PRODUCTION_TARGETS_INT = (len(data.status_flags),)
    for name, target in list(
        zip(CT_PRODUCTION_NAMES_INT, CT_PRODUCTION_TARGETS_INT, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target

    CT_PRODUCTION_TARGETS_STR = (data.metering_status,)
    for name, target in list(
        zip(CT_PRODUCTION_NAMES_STR, CT_PRODUCTION_TARGETS_STR, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert entity_state.state == target


CT_PRODUCTION_NAMES_FLOAT_PHASE = [
    f"{name}_{phase.lower()}"
    for phase in PHASENAMES
    for name in CT_PRODUCTION_NAMES_INT
]

CT_PRODUCTION_NAMES_STR_PHASE = [
    f"{name}_{phase.lower()}"
    for phase in PHASENAMES
    for name in CT_PRODUCTION_NAMES_STR
]


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_production_ct_phase_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test production ct phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    CT_PRODUCTION_NAMES_FLOAT_TARGET = [
        len(phase_data.status_flags)
        for phase_data in mock_envoy.data.ctmeter_production_phases.values()
    ]

    for name, target in list(
        zip(
            CT_PRODUCTION_NAMES_FLOAT_PHASE,
            CT_PRODUCTION_NAMES_FLOAT_TARGET,
            strict=False,
        )
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target

    CT_PRODUCTION_NAMES_STR_TARGET = [
        phase_data.metering_status
        for phase_data in mock_envoy.data.ctmeter_production_phases.values()
    ]

    for name, target in list(
        zip(
            CT_PRODUCTION_NAMES_STR_PHASE,
            CT_PRODUCTION_NAMES_STR_TARGET,
            strict=False,
        )
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert entity_state.state == target


CT_CONSUMPTION_NAMES_FLOAT: tuple[str, ...] = (
    "lifetime_net_energy_consumption",
    "lifetime_net_energy_production",
    "current_net_power_consumption",
    "frequency_net_consumption_ct",
    "voltage_net_consumption_ct",
    "meter_status_flags_active_net_consumption_ct",
)

CT_CONSUMPTION_NAMES_STR: tuple[str, ...] = ("metering_status_net_consumption_ct",)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_consumption_ct_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test consumption CT phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    data = mock_envoy.data.ctmeter_consumption

    CT_CONSUMPTION_TARGETS_FLOAT = (
        data.energy_delivered / 1000000.0,
        data.energy_received / 1000000.0,
        data.active_power / 1000.0,
        data.frequency,
        data.voltage,
        len(data.status_flags),
    )
    for name, target in list(
        zip(CT_CONSUMPTION_NAMES_FLOAT, CT_CONSUMPTION_TARGETS_FLOAT, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target

    CT_CONSUMPTION_TARGETS_STR = (data.metering_status,)
    for name, target in list(
        zip(CT_CONSUMPTION_NAMES_STR, CT_CONSUMPTION_TARGETS_STR, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert entity_state.state == target


CT_CONSUMPTION_NAMES_FLOAT_PHASE = [
    f"{name}_{phase.lower()}"
    for phase in PHASENAMES
    for name in CT_CONSUMPTION_NAMES_FLOAT
]

CT_CONSUMPTION_NAMES_STR_PHASE = [
    f"{name}_{phase.lower()}"
    for phase in PHASENAMES
    for name in CT_CONSUMPTION_NAMES_STR
]


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_consumption_ct_phase_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test consumption ct phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    CT_CONSUMPTION_NAMES_FLOAT_PHASE_TARGET = chain(
        *[
            (
                phase_data.energy_delivered / 1000000.0,
                phase_data.energy_received / 1000000.0,
                phase_data.active_power / 1000.0,
                phase_data.frequency,
                phase_data.voltage,
                len(phase_data.status_flags),
            )
            for phase_data in mock_envoy.data.ctmeter_consumption_phases.values()
        ]
    )

    for name, target in list(
        zip(
            CT_CONSUMPTION_NAMES_FLOAT_PHASE,
            CT_CONSUMPTION_NAMES_FLOAT_PHASE_TARGET,
            strict=False,
        )
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target

    CT_CONSUMPTION_NAMES_STR_PHASE_TARGET = [
        phase_data.metering_status
        for phase_data in mock_envoy.data.ctmeter_consumption_phases.values()
    ]

    for name, target in list(
        zip(
            CT_CONSUMPTION_NAMES_STR_PHASE,
            CT_CONSUMPTION_NAMES_STR_PHASE_TARGET,
            strict=False,
        )
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert entity_state.state == target


CT_STORAGE_NAMES_FLOAT = (
    "lifetime_battery_energy_discharged",
    "lifetime_battery_energy_charged",
    "current_battery_discharge",
    "voltage_storage_ct",
    "meter_status_flags_active_storage_ct",
)
CT_STORAGE_NAMES_STR = ("metering_status_storage_ct",)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_storage_ct_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test storage phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    data = mock_envoy.data.ctmeter_storage

    CT_STORAGE_TARGETS_FLOAT = (
        data.energy_delivered / 1000000.0,
        data.energy_received / 1000000.0,
        data.active_power / 1000.0,
        data.voltage,
        len(data.status_flags),
    )
    for name, target in list(
        zip(CT_STORAGE_NAMES_FLOAT, CT_STORAGE_TARGETS_FLOAT, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target

    CT_STORAGE_TARGETS_STR = (data.metering_status,)
    for name, target in list(
        zip(CT_STORAGE_NAMES_STR, CT_STORAGE_TARGETS_STR, strict=False)
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert entity_state.state == target


CT_STORAGE_NAMES_FLOAT_PHASE = [
    f"{name}_{phase.lower()}"
    for phase in PHASENAMES
    for name in (CT_STORAGE_NAMES_FLOAT)
]

CT_STORAGE_NAMES_STR_PHASE = [
    f"{name}_{phase.lower()}" for phase in PHASENAMES for name in (CT_STORAGE_NAMES_STR)
]


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_storage_ct_phase_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test storage ct phase entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    CT_STORAGE_NAMES_FLOAT_PHASE_TARGET = chain(
        *[
            (
                phase_data.energy_delivered / 1000000.0,
                phase_data.energy_received / 1000000.0,
                phase_data.active_power / 1000.0,
                phase_data.voltage,
                len(phase_data.status_flags),
            )
            for phase_data in mock_envoy.data.ctmeter_storage_phases.values()
        ]
    )

    for name, target in list(
        zip(
            CT_STORAGE_NAMES_FLOAT_PHASE,
            CT_STORAGE_NAMES_FLOAT_PHASE_TARGET,
            strict=False,
        )
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert float(entity_state.state) == target

    CT_STORAGE_NAMES_STR_PHASE_TARGET = [
        phase_data.metering_status
        for phase_data in mock_envoy.data.ctmeter_storage_phases.values()
    ]

    for name, target in list(
        zip(
            CT_STORAGE_NAMES_STR_PHASE,
            CT_STORAGE_NAMES_STR_PHASE_TARGET,
            strict=False,
        )
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{name}"))
        assert entity_state.state == target


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
    ],
    indirect=["mock_envoy"],
)
async def test_sensor_all_phase_entities_disabled_by_integration(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all phase entities are disabled by integration."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    assert all(
        f"{ENTITY_BASE}_{entity}"
        in (integration_disabled_entities(entity_registry, config_entry))
        for entity in (
            PRODUCTION_PHASE_NAMES
            + CONSUMPTION_PHASE_NAMES
            + CT_PRODUCTION_NAMES_FLOAT_PHASE
            + CT_PRODUCTION_NAMES_STR_PHASE
            + CT_CONSUMPTION_NAMES_FLOAT_PHASE
            + CT_CONSUMPTION_NAMES_STR_PHASE
        )
    )


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
    ],
    indirect=["mock_envoy"],
)
async def test_sensor_storage_phase_disabled_by_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_envoy: AsyncMock,
) -> None:
    """Test all storage CT phase entities are disabled by integration."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE: str = f"{Platform.SENSOR}.envoy_{sn}"

    assert all(
        f"{ENTITY_BASE}_{entity}"
        in integration_disabled_entities(entity_registry, config_entry)
        for entity in (CT_STORAGE_NAMES_FLOAT_PHASE + CT_STORAGE_NAMES_STR_PHASE)
    )


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_eu_batt",
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_inverter_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test enphase_envoy inverter entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    entity_base = f"{Platform.SENSOR}.inverter"

    for sn, inverter in mock_envoy.data.inverters.items():
        assert (entity_state := hass.states.get(f"{entity_base}_{sn}"))
        assert float(entity_state.state) == (inverter.last_report_watts)
        assert (last_reported := hass.states.get(f"{entity_base}_{sn}_last_reported"))
        assert dt_util.parse_datetime(
            last_reported.state
        ) == dt_util.utc_from_timestamp(inverter.last_report_date)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_eu_batt",
        "envoy_metered_batt_relay",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=["mock_envoy"],
)
async def test_sensor_inverter_disabled_by_integration(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test enphase_envoy inverter disabled by integration entities."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    INVERTER_BASE = f"{Platform.SENSOR}.inverter"

    assert all(
        f"{INVERTER_BASE}_{sn}_last_reported"
        in integration_disabled_entities(entity_registry, config_entry)
        for sn in mock_envoy.data.inverters
    )


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
    ],
    indirect=["mock_envoy"],
)
async def test_sensor_encharge_aggregate_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test enphase_envoy encharge aggregate entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.serial_number
    ENTITY_BASE = f"{Platform.SENSOR}.envoy_{sn}"

    data = mock_envoy.data.encharge_aggregate

    for target in (
        ("battery", data.state_of_charge),
        ("reserve_battery_level", data.reserve_state_of_charge),
        ("available_battery_energy", data.available_energy),
        ("reserve_battery_energy", data.backup_reserve),
        ("battery_capacity", data.max_available_capacity),
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{target[0]}"))
        assert float(entity_state.state) == target[1]


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
    ],
    indirect=["mock_envoy"],
)
async def test_sensor_encharge_enpower_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test enphase_envoy encharge enpower entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.data.enpower.serial_number
    ENTITY_BASE = f"{Platform.SENSOR}.enpower"

    assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{sn}_temperature"))
    assert (
        round(
            TemperatureConverter.convert(
                float(entity_state.state),
                hass.config.units.temperature_unit,
                UnitOfTemperature.FAHRENHEIT
                if mock_envoy.data.enpower.temperature_unit == "F"
                else UnitOfTemperature.CELSIUS,
            )
        )
        == mock_envoy.data.enpower.temperature
    )
    assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{sn}_last_reported"))
    assert dt_util.parse_datetime(entity_state.state) == dt_util.utc_from_timestamp(
        mock_envoy.data.enpower.last_report_date
    )


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
    ],
    indirect=["mock_envoy"],
)
async def test_sensor_encharge_power_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
) -> None:
    """Test enphase_envoy encharge_power entities values."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    ENTITY_BASE = f"{Platform.SENSOR}.encharge"

    ENCHARGE_POWER_NAMES = (
        "battery",
        "apparent_power",
        "power",
    )

    ENCHARGE_POWER_TARGETS = [
        (
            sn,
            (
                encharge_power.soc,
                encharge_power.apparent_power_mva / 1000.0,
                encharge_power.real_power_mw / 1000.0,
            ),
        )
        for sn, encharge_power in mock_envoy.data.encharge_power.items()
    ]

    for sn, sn_target in ENCHARGE_POWER_TARGETS:
        for name, target in list(zip(ENCHARGE_POWER_NAMES, sn_target, strict=False)):
            assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{sn}_{name}"))
            assert float(entity_state.state) == target

    for sn, encharge_inventory in mock_envoy.data.encharge_inventory.items():
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{sn}_temperature"))
        assert (
            round(
                TemperatureConverter.convert(
                    float(entity_state.state),
                    hass.config.units.temperature_unit,
                    UnitOfTemperature.FAHRENHEIT
                    if encharge_inventory.temperature_unit == "F"
                    else UnitOfTemperature.CELSIUS,
                )
            )
            == encharge_inventory.temperature
        )
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{sn}_last_reported"))
        assert dt_util.parse_datetime(entity_state.state) == dt_util.utc_from_timestamp(
            encharge_inventory.last_report_date
        )


def integration_disabled_entities(
    entity_registry: er.EntityRegistry, config_entry: MockConfigEntry
) -> list[str]:
    """Return list of entity ids marked as disabled by integration."""
    return [
        entity_entry.entity_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    ]


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_missing_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test enphase_envoy sensor platform midding data handling."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    ENTITY_BASE = f"{Platform.SENSOR}.envoy_{mock_envoy.serial_number}"

    # force missing data to test 'if == none' code sections
    mock_envoy.data.system_production_phases["L2"] = None
    mock_envoy.data.system_consumption_phases["L2"] = None
    mock_envoy.data.system_net_consumption_phases["L2"] = None
    mock_envoy.data.ctmeter_production = None
    mock_envoy.data.ctmeter_consumption = None
    mock_envoy.data.ctmeter_storage = None
    mock_envoy.data.ctmeter_production_phases = None
    mock_envoy.data.ctmeter_consumption_phases = None
    mock_envoy.data.ctmeter_storage_phases = None

    # use different inverter serial to test 'expected inverter missing' code
    mock_envoy.data.inverters["2"] = mock_envoy.data.inverters.pop("1")

    # force HA to detect changed data by changing raw
    mock_envoy.data.raw = {"I": "am changed"}

    # MOve time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # all these should now be in unknown state
    for entity in (
        "lifetime_energy_production_l2",
        "lifetime_energy_consumption_l2",
        "metering_status_production_ct",
        "metering_status_net_consumption_ct",
        "metering_status_storage_ct",
        "metering_status_production_ct_l2",
        "metering_status_net_consumption_ct_l2",
        "metering_status_storage_ct_l2",
    ):
        assert (entity_state := hass.states.get(f"{ENTITY_BASE}_{entity}"))
        assert entity_state.state == STATE_UNKNOWN

    # test the original inverter is now unknown
    assert (entity_state := hass.states.get("sensor.inverter_1"))
    assert entity_state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy_metered_batt_relay",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fw_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enphase_envoy sensor update over fw update."""
    logging.getLogger("homeassistant.components.enphase_envoy").setLevel(logging.DEBUG)
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    # force HA to detect changed data by changing raw
    mock_envoy.firmware = "0.0.0"

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "firmware changed from: " in caplog.text
    assert "to: 0.0.0, reloading enphase envoy integration" in caplog.text
