"""Test Satel Integra Binary Sensor."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    snapshot_platform,
)
from satel_integra import (
    SatelRtcAndStatus,
    SatelSystemTroubles,
    SatelTrouble,
    SatelTroubleType,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    get_output_changed_callback,
    get_system_status_callback,
    get_zone_changed_callback,
    setup_integration,
    trigger_connection_status_update,
)

SPECIFIC_TROUBLE_CASES = (
    ("output_1_trouble", SatelTrouble(SatelTroubleType.OUTPUT, source_id=1)),
    ("output_2_trouble", SatelTrouble(SatelTroubleType.OUTPUT, source_id=2)),
    ("output_3_trouble", SatelTrouble(SatelTroubleType.OUTPUT, source_id=3)),
    ("output_4_trouble", SatelTrouble(SatelTroubleType.OUTPUT, source_id=4)),
    ("keypad_power_supply_trouble", SatelTrouble(SatelTroubleType.KEYPAD_POWER_SUPPLY)),
    (
        "expander_power_supply_trouble",
        SatelTrouble(SatelTroubleType.EXPANDER_POWER_SUPPLY),
    ),
    ("panel_battery_trouble", SatelTrouble(SatelTroubleType.PANEL_BATTERY)),
    ("panel_ac_trouble", SatelTrouble(SatelTroubleType.PANEL_AC)),
    ("dt1_trouble", SatelTrouble(SatelTroubleType.DT1)),
    ("dt2_trouble", SatelTrouble(SatelTroubleType.DT2)),
    ("dtm_trouble", SatelTrouble(SatelTroubleType.DTM)),
    ("rtc_trouble", SatelTrouble(SatelTroubleType.RTC)),
    (
        "external_device_dtr_trouble",
        SatelTrouble(SatelTroubleType.EXTERNAL_DEVICE_DTR),
    ),
    (
        "panel_battery_missing_trouble",
        SatelTrouble(SatelTroubleType.PANEL_BATTERY_MISSING),
    ),
    (
        "external_modem_initialization_trouble",
        SatelTrouble(SatelTroubleType.EXTERNAL_MODEM_INITIALIZATION),
    ),
    (
        "external_modem_command_trouble",
        SatelTrouble(SatelTroubleType.EXTERNAL_MODEM_COMMAND),
    ),
    (
        "telephone_line_voltage_or_auxiliary_processor_trouble",
        SatelTrouble(SatelTroubleType.TELEPHONE_LINE_VOLTAGE_OR_AUXILIARY_PROCESSOR),
    ),
    (
        "telephone_line_bad_signal_trouble",
        SatelTrouble(SatelTroubleType.TELEPHONE_LINE_BAD_SIGNAL),
    ),
    (
        "telephone_line_no_signal_trouble",
        SatelTrouble(SatelTroubleType.TELEPHONE_LINE_NO_SIGNAL),
    ),
    (
        "monitoring_station_1_trouble",
        SatelTrouble(SatelTroubleType.MONITORING_STATION, source_id=1),
    ),
    (
        "monitoring_station_2_trouble",
        SatelTrouble(SatelTroubleType.MONITORING_STATION, source_id=2),
    ),
    (
        "eeprom_or_rtc_access_trouble",
        SatelTrouble(SatelTroubleType.EEPROM_OR_RTC_ACCESS),
    ),
    ("ram_trouble", SatelTrouble(SatelTroubleType.RAM)),
    (
        "panel_restart_memory_trouble",
        SatelTrouble(SatelTroubleType.PANEL_RESTART_MEMORY),
    ),
)

DISABLED_TROUBLE_KEYS = tuple(
    key
    for key, _ in SPECIFIC_TROUBLE_CASES
    if key not in {"panel_ac_trouble", "panel_battery_trouble"}
)


@pytest.fixture(autouse=True)
async def binary_sensor_only() -> AsyncGenerator[None]:
    """Enable only the binary sensor platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_satel")
async def test_binary_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test binary sensors correctly being set up."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_with_subentries.entry_id
    )

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890_zones_1"), mock_config_entry_with_subentries.entry_id
    )

    assert device_entry == snapshot(name="device-zone")

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890_outputs_1"), mock_config_entry_with_subentries.entry_id
    )
    assert device_entry == snapshot(name="device-output")


@pytest.mark.parametrize(
    ("device_state", "expected_state"),
    [
        (None, STATE_UNKNOWN),
        (False, STATE_OFF),
        (True, STATE_ON),
    ],
)
async def test_binary_sensor_initial_state(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    device_state: bool | None,
    expected_state: str,
) -> None:
    """Test binary sensors have a correct initial state after initialization."""

    # Instantly call callback to ensure we have initial data set
    async def mock_start(**_: object) -> None:
        mock_satel.state.outputs[1].active = device_state
        mock_satel.state.zones[1].violated = device_state
        get_output_changed_callback(mock_satel)()
        get_zone_changed_callback(mock_satel)()

    mock_satel.start = AsyncMock(side_effect=mock_start)

    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("binary_sensor.zone").state == expected_state
    assert hass.states.get("binary_sensor.output").state == expected_state


async def test_binary_sensor_callback(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test binary sensors correctly change state after a callback from the panel."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF

    zone_update_method = get_zone_changed_callback(mock_satel)
    output_update_method = get_output_changed_callback(mock_satel)

    mock_satel.state.outputs[1].active = True
    mock_satel.state.zones[1].violated = True
    output_update_method()
    zone_update_method()
    assert hass.states.get("binary_sensor.zone").state == STATE_ON
    assert hass.states.get("binary_sensor.output").state == STATE_ON

    mock_satel.state.outputs[1].active = False
    mock_satel.state.zones[1].violated = False
    output_update_method()
    zone_update_method()
    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF


@pytest.mark.parametrize(
    ("key", "service_mode", "troubles"),
    [
        ("system_trouble", False, True),
        ("service_mode", True, False),
    ],
)
async def test_system_status_sensor(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    key: str,
    service_mode: bool,
    troubles: bool,
) -> None:
    """Test system status sensors follow panel status updates."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        f"{mock_config_entry_with_subentries.entry_id}_{key}",
    )
    assert entity_id is not None
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is EntityCategory.DIAGNOSTIC

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    mock_satel.state.system_status = SatelRtcAndStatus(
        service_mode=service_mode,
        troubles=troubles,
        acu_100_present=False,
        int_rx_present=False,
        troubles_memory=False,
        grade_2_or_3=False,
    )
    get_system_status_callback(mock_satel)()

    assert hass.states.is_state(entity_id, STATE_ON)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(("key", "trouble"), SPECIFIC_TROUBLE_CASES)
async def test_specific_system_trouble_sensor(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    key: str,
    trouble: SatelTrouble,
) -> None:
    """Test specific system trouble sensors follow trouble updates."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        f"{mock_config_entry_with_subentries.entry_id}_{key}",
    )
    assert entity_id is not None
    assert hass.states.is_state(entity_id, STATE_OFF)

    mock_satel.state.system_troubles = SatelSystemTroubles(
        troubles=frozenset({trouble})
    )
    get_system_status_callback(mock_satel)()

    assert hass.states.is_state(entity_id, STATE_ON)
    for other_key, _ in SPECIFIC_TROUBLE_CASES:
        if other_key == key:
            continue
        other_entity_id = entity_registry.async_get_entity_id(
            "binary_sensor",
            DOMAIN,
            f"{mock_config_entry_with_subentries.entry_id}_{other_key}",
        )
        assert other_entity_id is not None
        assert hass.states.is_state(other_entity_id, STATE_OFF)


async def test_other_specific_trouble_sensors_disabled_by_default(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
) -> None:
    """Test other specific trouble sensors are disabled by default."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    for key in DISABLED_TROUBLE_KEYS:
        entity_id = entity_registry.async_get_entity_id(
            "binary_sensor",
            DOMAIN,
            f"{mock_config_entry_with_subentries.entry_id}_{key}",
        )
        assert entity_id is not None
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_binary_sensor_last_reported(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensors update last_reported if same state is reported."""
    events = async_capture_events(hass, "state_changed")
    await setup_integration(hass, mock_config_entry_with_subentries)

    first_reported = hass.states.get("binary_sensor.zone").last_reported
    assert first_reported is not None
    # Initial state change events for four system sensors, zone, and output
    assert len(events) == 4

    freezer.tick(1)
    async_fire_time_changed(hass)

    # Run callbacks with same payload
    zone_update_method = get_zone_changed_callback(mock_satel)
    output_update_method = get_output_changed_callback(mock_satel)
    system_status_update_method = get_system_status_callback(mock_satel)
    output_update_method()
    zone_update_method()
    system_status_update_method()

    assert first_reported != hass.states.get("binary_sensor.zone").last_reported
    assert len(events) == 4  # last_reported shall not fire state_changed


@pytest.mark.parametrize("unique_id_suffix", ["zones_1", "system_trouble"])
async def test_availability(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    unique_id_suffix: str,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        f"{mock_config_entry_with_subentries.entry_id}_{unique_id_suffix}",
    )
    assert entity_id is not None
    assert hass.states.is_state(entity_id, STATE_OFF)

    await trigger_connection_status_update(hass, mock_satel, False)

    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    await trigger_connection_status_update(hass, mock_satel, True)

    assert hass.states.is_state(entity_id, STATE_OFF)
