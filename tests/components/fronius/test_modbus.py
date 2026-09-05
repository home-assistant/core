"""Tests for the Fronius Modbus TCP (SunSpec) support."""

from datetime import timedelta
from logging import ERROR
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from fronius_modbus import Mppt
from fronius_modbus.testing import MpptModuleSpec, build_sunspec_map
from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.fronius.const import DOMAIN, SOLAR_NET_RESCAN_TIMER
from homeassistant.components.fronius.coordinator import (
    FroniusModbusInverterUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_HOST, mock_responses, setup_fronius_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

# module names as reported by real GEN24 hybrid inverters
GEN24_HYBRID_MODULES = [
    MpptModuleSpec(
        id_str="MPPT 1", current=82, voltage=4021, power=3300, energy=1_000_000
    ),
    MpptModuleSpec(
        id_str="MPPT 2", current=41, voltage=4022, power=1650, energy=500_000
    ),
    MpptModuleSpec(id_str="StCha 3", current=0, voltage=0, power=0, energy=200_000),
    MpptModuleSpec(
        id_str="StDisCha 4", current=12, voltage=3990, power=480, energy=150_000
    ),
]


def assert_state(
    hass: HomeAssistant, entity_id: str, expected_state: str | float
) -> None:
    """Assert the state of an entity."""
    state = hass.states.get(entity_id)
    assert state, f"State for {entity_id} not found"
    assert state.state == str(expected_state)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "float_mode",
    [pytest.param(True, id="float"), pytest.param(False, id="int_sf")],
)
async def test_gen24_storage_mppt(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    entity_registry: er.EntityRegistry,
    float_mode: bool,
) -> None:
    """Test MPPT entities of a GEN24 hybrid inverter for both data types."""
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map(
            GEN24_HYBRID_MODULES, float_mode=float_mode, storage_wcha_max=5000
        )
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SENSOR]):
        config_entry = await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )
    assert config_entry.state is ConfigEntryState.LOADED

    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_current", 8.2)
    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_voltage", 402.1)
    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_power", 3300)
    assert_state(hass, "sensor.gen24_storage_mppt_1_energy", 1000000)
    assert_state(hass, "sensor.gen24_storage_mppt_2_dc_power", 1650)
    assert_state(hass, "sensor.gen24_storage_mppt_3_dc_power", 0)
    assert_state(hass, "sensor.gen24_storage_mppt_4_dc_power", 480)

    # derived totals: PV strings only, charge/discharge from storage modules
    assert_state(hass, "sensor.gen24_storage_pv_energy_total", 1500000)
    assert_state(hass, "sensor.gen24_storage_battery_charging_energy_total", 200000)
    assert_state(hass, "sensor.gen24_storage_battery_discharging_energy_total", 150000)

    entity_entry = entity_registry.async_get("sensor.gen24_storage_mppt_1_dc_power")
    assert entity_entry
    assert entity_entry.unique_id == "12345678-modbus-mppt_1_power_dc"

    solar_net = config_entry.runtime_data
    assert len(solar_net.modbus_inverter_coordinators) == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("storage_id_str", "expected_pv_energy_total"),
    [
        # a bidirectional storage module is excluded from the PV total
        pytest.param("Battery 1", 1000000, id="storage_matched_by_id_str"),
        # 2-module inverters default to PV even with a detected storage -
        # safe since Symo Hybrid doesn't support lifetime energy anyway
        pytest.param("String 2", 1500000, id="inconclusive_defaults_to_pv"),
    ],
)
async def test_hybrid_bidirectional_storage(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    storage_id_str: str,
    expected_pv_energy_total: int,
) -> None:
    """Test 2-module inverters with a detected storage.

    No separate charge/discharge energy is available in either case.
    """
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map(
            [
                MpptModuleSpec(
                    id_str="String 1",
                    current=82,
                    voltage=4021,
                    power=3300,
                    energy=1_000_000,
                ),
                MpptModuleSpec(
                    id_str=storage_id_str,
                    current=41,
                    voltage=4022,
                    power=1650,
                    energy=500_000,
                ),
            ],
            storage_wcha_max=5000,
        )
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SENSOR]):
        await setup_fronius_integration(hass, is_logger=False, unique_id="12345678")

    assert_state(hass, "sensor.gen24_storage_pv_energy_total", expected_pv_energy_total)
    assert_state(hass, "sensor.gen24_storage_mppt_2_dc_power", 1650)
    # no separable charge/discharge energy without dedicated modules
    assert hass.states.get("sensor.gen24_storage_battery_charging_energy_total") is None
    assert (
        hass.states.get("sensor.gen24_storage_battery_discharging_energy_total") is None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_datamanager_multiple_inverters(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test Modbus entities for multiple inverters behind a Datamanager."""
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map(
            [
                MpptModuleSpec(
                    id_str="String 1",
                    current=82,
                    voltage=4021,
                    power=3300,
                    energy=1_000_000,
                ),
                MpptModuleSpec(
                    id_str="String 2",
                    current=41,
                    voltage=4022,
                    power=1650,
                    energy=500_000,
                ),
            ]
        )
    )
    mock_fronius_modbus.for_unit(2).holding.update(
        build_sunspec_map(
            [
                MpptModuleSpec(
                    id_str="String 1",
                    current=50,
                    voltage=3000,
                    power=1500,
                    energy=250_000,
                ),
            ]
        )
    )
    mock_responses(aioclient_mock, fixture_set="primo_s0", inverter_ids=[1, 2])
    await setup_fronius_integration(hass, is_logger=True)

    assert_state(hass, "sensor.primo_5_0_1_mppt_1_dc_power", 3300)
    assert_state(hass, "sensor.primo_5_0_1_mppt_2_dc_power", 1650)
    assert_state(hass, "sensor.primo_5_0_1_pv_energy_total", 1500000)
    assert_state(hass, "sensor.primo_3_0_1_mppt_1_dc_power", 1500)
    assert_state(hass, "sensor.primo_3_0_1_pv_energy_total", 250000)
    # no storage in this system - no charge/discharge entities
    assert hass.states.get("sensor.primo_5_0_1_battery_charging_energy_total") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_custom_modbus_port(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    mock_modbus_unavailable: MagicMock,
) -> None:
    """Test the unit is asked for on the configured Modbus port."""
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map(GEN24_HYBRID_MODULES, storage_wcha_max=5000)
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SENSOR]):
        await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678", modbus_port=1502
        )

    params = mock_modbus_unavailable.call_args.args[2]
    assert params.host == "fronius"
    assert params.port == 1502
    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_power", 3300)


async def test_modbus_unavailable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entry loads HTTP-only when the Modbus probe is refused."""
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    config_entry = await setup_fronius_integration(
        hass, is_logger=False, unique_id="12345678"
    )
    assert config_entry.state is ConfigEntryState.LOADED

    assert not config_entry.runtime_data.modbus_inverter_coordinators
    assert not [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if "-modbus-" in entry.unique_id
    ]


async def test_no_mppt_model(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a SunSpec device without MPPT model still gets its controls.

    The power limit and battery setpoints live in their own models, so they
    do not depend on the MPPT data being there.
    """
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map([], include_mppt_model=False)
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    config_entry = await setup_fronius_integration(
        hass, is_logger=False, unique_id="12345678"
    )
    assert config_entry.state is ConfigEntryState.LOADED

    assert config_entry.runtime_data.modbus_inverter_coordinators == []
    modbus_entities = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if "-modbus-" in entry.unique_id
    ]
    # no MPPT sensors, but the controls and their derived values are there
    assert not [entry for entry in modbus_entities if "mppt" in entry.unique_id]
    assert "number" in {entry.domain for entry in modbus_entities}

    freezer.tick(timedelta(minutes=SOLAR_NET_RESCAN_TIMER, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # the re-scan finds the controls already set up
    assert len(config_entry.runtime_data.modbus_settings_coordinators) == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_not_implemented_values(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test not-implemented sentinel values don't create entities."""
    modules = [
        MpptModuleSpec(
            id_str="String 1", current=82, voltage=4021, power=3300, energy=1_000_000
        ),
        # all values not implemented
        MpptModuleSpec(id_str="String 2"),
    ]
    unit = mock_fronius_modbus.for_unit(1)
    unit.holding.update(build_sunspec_map(modules))
    mock_responses(aioclient_mock, fixture_set="gen24")
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SENSOR]):
        await setup_fronius_integration(hass, is_logger=False)

    assert_state(hass, "sensor.inverter_name_mppt_1_dc_power", 3300)
    assert hass.states.get("sensor.inverter_name_mppt_2_dc_power") is None
    assert hass.states.get("sensor.inverter_name_mppt_2_energy") is None
    # PV total unknown when a PV module doesn't report energy
    assert hass.states.get("sensor.inverter_name_pv_energy_total") is None

    # an implemented value turning into a sentinel becomes unknown
    modules[0].energy = 0
    unit.holding.clear()
    unit.holding.update(build_sunspec_map(modules))
    freezer.tick(FroniusModbusInverterUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert_state(hass, "sensor.inverter_name_mppt_1_energy", "unknown")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_data_type_changed_at_runtime(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test re-discovery when the register map shifts due to a data type change."""
    unit = mock_fronius_modbus.for_unit(1)
    unit.holding.update(build_sunspec_map(GEN24_HYBRID_MODULES, float_mode=True))
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SENSOR]):
        await setup_fronius_integration(hass, is_logger=False, unique_id="12345678")
    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_power", 3300)

    # switching int+SF shifts the model 160 address
    unit.holding.clear()
    unit.holding.update(build_sunspec_map(GEN24_HYBRID_MODULES, float_mode=False))
    freezer.tick(FroniusModbusInverterUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_power", 3300)

    # a broken register map makes the update fail and entities unavailable
    unit.holding.clear()
    freezer.tick(FroniusModbusInverterUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_power", "unavailable")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_connection_lost_recovers(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a dropped Modbus link heals without reloading the entry.

    The connection re-establishes a dropped link on the next request, so
    entities recover on the next poll.
    """
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map(GEN24_HYBRID_MODULES)
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SENSOR]):
        config_entry = await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )
    assert config_entry.runtime_data.modbus_inverter_coordinators

    mock_fronius_modbus.simulate_connection_lost()
    await hass.async_block_till_done()

    freezer.tick(FroniusModbusInverterUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # the entry was not reloaded and the values are back
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.modbus_inverter_coordinators
    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_power", 3300)


async def test_modbus_retried_after_setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_modbus_unavailable: MagicMock,
    mock_modbus_connection: MockModbusConnection,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an inverter asleep at setup time gets its Modbus entities later.

    An inverter without a grid-powered datalogger answers nothing while it is
    powered down, so discovery fails and the re-scan has to try again.
    """
    unit = mock_modbus_connection.for_unit(1)
    unit.holding.update(build_sunspec_map(GEN24_HYBRID_MODULES))
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SENSOR]):
        config_entry = await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )
    assert not config_entry.runtime_data.modbus_inverter_coordinators
    assert hass.states.get("sensor.gen24_storage_mppt_1_dc_power") is None

    # the inverter wakes up and starts answering
    mock_modbus_unavailable.side_effect = lambda hass, entry, params, unit_id: (
        mock_modbus_connection.for_unit(unit_id)
    )
    unit.fail_requests(None)

    freezer.tick(timedelta(minutes=SOLAR_NET_RESCAN_TIMER, seconds=1))
    async_fire_time_changed(hass)
    # the re-scan refreshes the new coordinator in a background task
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.runtime_data.modbus_inverter_coordinators
    assert_state(hass, "sensor.gen24_storage_mppt_1_dc_power", 3300)
    # the Modbus sensors of the re-scan are told apart from the SolarAPI ones
    entry = entity_registry.async_get("sensor.gen24_storage_mppt_1_dc_power")
    assert entry
    assert "-modbus-" in entry.unique_id
    # the hold on the shared connection is taken once, not once per re-scan
    assert mock_modbus_unavailable.call_count == 1


async def test_control_refused_creates_no_control_entities(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device that rejects writes gets readings but no controls.

    "Inverter control via Modbus" has to be enabled on the device web
    interface; without it every write is refused, so offering the controls
    would only produce entities that error when used.
    """
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map(GEN24_HYBRID_MODULES, storage_wcha_max=5000)
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch(
        "fronius_modbus.Controls.probe_write_access", AsyncMock(return_value=False)
    ):
        config_entry = await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )

    assert config_entry.runtime_data.modbus_settings_coordinators == []
    assert not [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == "number"
    ]


async def test_controls_enabled_later_get_their_entities(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entities appear for controls a re-scan finds after setup.

    The platforms are set up once, so a coordinator that only comes up on a
    later re-scan has to be handed to them through the dispatcher - which
    every platform listens to, including those it has nothing for.
    """
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map([], include_mppt_model=False)
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch(
        "fronius_modbus.Controls.probe_write_access", AsyncMock(return_value=False)
    ):
        config_entry = await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )
    assert hass.states.get("number.gen24_storage_ac_power_limit") is None

    # inverter control via Modbus is enabled on the device web interface
    freezer.tick(timedelta(minutes=SOLAR_NET_RESCAN_TIMER, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.runtime_data.modbus_settings_coordinators
    assert hass.states.get("number.gen24_storage_ac_power_limit")
    assert hass.states.get("switch.gen24_storage_ac_power_limiting")
    assert not [record for record in caplog.records if record.levelno >= ERROR]


async def test_readings_recover_when_only_the_controls_came_up(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a re-scan still adds the MPPT data after it failed once.

    The two coordinators are independent: one of them answering is no reason
    to stop retrying the other.
    """
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map(GEN24_HYBRID_MODULES, storage_wcha_max=12800)
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch.object(
        Mppt, "async_update", side_effect=ModbusConnectionError("no answer")
    ):
        config_entry = await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )
        assert not config_entry.runtime_data.modbus_inverter_coordinators
        assert config_entry.runtime_data.modbus_settings_coordinators

    freezer.tick(timedelta(minutes=SOLAR_NET_RESCAN_TIMER, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.runtime_data.modbus_inverter_coordinators
    # the settings coordinator that was already up is not added a second time
    assert len(config_entry.runtime_data.modbus_settings_coordinators) == 1


async def test_wrongly_registered_sensors_are_moved_over(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test 2026.9 Modbus sensors keep their entity ID and history.

    A re-scan registered them with the SolarAPI unique ID format, which the
    fixed platform would otherwise leave behind as a stale entity.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="f1e2b9837e8adaed6fa682acaa216fd8",
        unique_id="12345678",
        data={CONF_HOST: MOCK_HOST, "is_logger": False, "modbus_port": 502},
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    stale = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "12345678-mppt_1_power_dc",
        config_entry=config_entry,
        suggested_object_id="gen24_storage_mppt_1_dc_power",
    )
    untouched = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "12345678-energy_total",
        config_entry=config_entry,
        suggested_object_id="gen24_storage_total_energy",
    )
    # a restart has already registered a second entity for this one
    superseded = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "12345678-mppt_2_power_dc",
        config_entry=config_entry,
        suggested_object_id="gen24_storage_mppt_2_dc_power_old",
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "12345678-modbus-mppt_2_power_dc",
        config_entry=config_entry,
        suggested_object_id="gen24_storage_mppt_2_dc_power",
    )
    mock_fronius_modbus.for_unit(1).holding.update(
        build_sunspec_map(GEN24_HYBRID_MODULES, storage_wcha_max=12800)
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (entry := entity_registry.async_get(stale.entity_id))
    assert entry.unique_id == "12345678-modbus-mppt_1_power_dc"
    # a SolarAPI sensor keeps its own format
    assert (entry := entity_registry.async_get(untouched.entity_id))
    assert entry.unique_id == "12345678-energy_total"
    # and one whose place is taken is left where it is
    assert (entry := entity_registry.async_get(superseded.entity_id))
    assert entry.unique_id == "12345678-mppt_2_power_dc"
