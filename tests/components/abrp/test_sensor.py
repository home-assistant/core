"""Tests for the A Better Routeplanner sensor platform."""

import logging
from unittest.mock import MagicMock

from aioabrp import ChargingState, ConnectionEvent, ConnectionState, Telemetry
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    build_metric_value,
    fire_connection,
    fire_frame,
)

SOC_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_soc"
POWER_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_power"
VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"
CHARGING_STATE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_charging_state"
VOLTAGE_ENTITY_ID_2 = "sensor.rivian_r1s_2024_quad_max_voltage"
# Not in the mocked garage, so the stream never subscribes to it.
_ABSENT_VEHICLE_ID = 999999999999


@pytest.mark.usefixtures("mock_abrp_client")
async def test_telemetry_sensors_snapshot(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Entity registry + states snapshot for the full per-vehicle metric set."""
    await setup_integration(hass, config_entry_with_vehicles)

    # Every metric in one frame so the snapshot captures rendered states.
    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(
            soc=build_metric_value(85.0),
            power=build_metric_value(23300.0),
            voltage=build_metric_value(704.0),
            soe=build_metric_value(68000.0),
            odometer=build_metric_value(120000.0),
            calibrated_ref_cons=build_metric_value(175.0),
            battery_capacity=build_metric_value(92000.0),
            soh=build_metric_value(98.0),
            range=build_metric_value(100000.0),
            battery_temperature=build_metric_value(23.7),
            charging_state=build_metric_value(ChargingState.CHARGING_AC),
        ),
    )
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_vehicles.entry_id
    )


@pytest.mark.parametrize(
    ("charging_state", "expected_option"),
    [
        pytest.param(ChargingState.CHARGING_AC, "charging_ac", id="charging_ac"),
        pytest.param(ChargingState.CHARGING_DC, "charging_dc", id="charging_dc"),
        pytest.param(
            ChargingState.CHARGING_UNKNOWN, "charging_unknown", id="charging_unknown"
        ),
        pytest.param(ChargingState.NOT_CHARGING, "not_charging", id="not_charging"),
        pytest.param(ChargingState.PLUGGED_IN, "plugged_in", id="plugged_in"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client")
async def test_charging_state_lazy_create_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    charging_state: ChargingState,
    expected_option: str,
) -> None:
    """First ``charging_state`` frame after setup lazily creates the enum sensor."""
    await setup_integration(hass, config_entry_with_vehicles)

    assert hass.states.get(CHARGING_STATE_ENTITY_ID) is None

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(charging_state=build_metric_value(charging_state)),
    )
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_option


@pytest.mark.usefixtures("mock_abrp_client")
async def test_availability_follows_stream_auth_not_connection(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Idle disconnects keep values; a terminal auth failure hides them until reconnect."""
    await setup_integration(hass, config_entry_with_vehicles)
    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(12000.0)),
    )
    await hass.async_block_till_done()

    fire_connection(
        mock_telemetry_stream,
        ConnectionEvent(ConnectionState.DISCONNECTED, "idle close"),
    )
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "12000.0"

    for _ in range(2):
        fire_connection(
            mock_telemetry_stream, ConnectionEvent(ConnectionState.AUTH_FAILED, "401")
        )
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "unavailable"
    assert [
        record.levelno for record in caplog.records if "auth failed" in record.message
    ] == [logging.WARNING]
    assert any(config_entry_with_vehicles.async_get_active_flows(hass, {SOURCE_REAUTH}))

    fire_connection(
        mock_telemetry_stream,
        ConnectionEvent(ConnectionState.DISCONNECTED, "idle close"),
    )
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "unavailable"

    fire_connection(mock_telemetry_stream, ConnectionEvent(ConnectionState.CONNECTED))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "12000.0"


@pytest.mark.parametrize(
    ("telemetry", "created", "absent"),
    [
        pytest.param(
            Telemetry(power=build_metric_value(1234.0)),
            POWER_ENTITY_ID,
            (SOC_ENTITY_ID, VOLTAGE_ENTITY_ID),
            id="power",
        ),
        pytest.param(
            Telemetry(voltage=build_metric_value(400.0)),
            VOLTAGE_ENTITY_ID,
            (SOC_ENTITY_ID, POWER_ENTITY_ID),
            id="voltage",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client")
async def test_first_frame_creates_only_that_metric(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
    telemetry: Telemetry,
    created: str,
    absent: tuple[str, ...],
) -> None:
    """No sensor exists until its metric arrives, and only that one is created."""
    await setup_integration(hass, config_entry_with_vehicles)
    assert entity_registry.async_get(created) is None

    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, telemetry)
    await hass.async_block_till_done()

    assert entity_registry.async_get(created) is not None
    assert [entity_registry.async_get(entity_id) for entity_id in absent] == [
        None
    ] * len(absent)


@pytest.mark.usefixtures("mock_abrp_client")
async def test_lazy_create_idempotent_on_repeated_frames(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Frames merge per vehicle, and a repeated metric reuses its entity."""
    await setup_integration(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(5000.0)),
    )
    await hass.async_block_till_done()

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(soc=build_metric_value(85.0)),
    )
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "5000.0"
    assert hass.states.get(SOC_ENTITY_ID).state == "85.0"

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(6000.0)),
    )
    await hass.async_block_till_done()

    all_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry_with_vehicles.entry_id
    )
    power_entries = [e for e in all_entries if e.entity_id == POWER_ENTITY_ID]
    assert len(power_entries) == 1

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "6000.0"
    # HA would otherwise reject a re-created entity, so only the log shows it.
    assert "already exists" not in caplog.text


@pytest.mark.parametrize(
    ("active_vehicle_id", "expected_entity_id", "other_vehicle_id", "other_entity_id"),
    [
        pytest.param(
            MOCK_VEHICLE_ID,
            VOLTAGE_ENTITY_ID,
            MOCK_VEHICLE_ID_2,
            VOLTAGE_ENTITY_ID_2,
            id="vehicle_a_active",
        ),
        pytest.param(
            MOCK_VEHICLE_ID_2,
            VOLTAGE_ENTITY_ID_2,
            MOCK_VEHICLE_ID,
            VOLTAGE_ENTITY_ID,
            id="vehicle_b_active",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client")
async def test_multi_vehicle_entity_isolation(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
    active_vehicle_id: int,
    expected_entity_id: str,
    other_vehicle_id: int,
    other_entity_id: str,
) -> None:
    """Each vehicle gets its own sensors and values; ids outside the garage get none."""
    await setup_integration(hass, config_entry_with_vehicles)

    for vehicle_id in (active_vehicle_id, _ABSENT_VEHICLE_ID):
        fire_frame(
            mock_telemetry_stream,
            vehicle_id,
            Telemetry(voltage=build_metric_value(400.0)),
        )
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, config_entry_with_vehicles.entry_id
    )
    assert [entry.entity_id for entry in entries] == [expected_entity_id]

    fire_frame(
        mock_telemetry_stream,
        other_vehicle_id,
        Telemetry(voltage=build_metric_value(380.0)),
    )
    await hass.async_block_till_done()
    assert hass.states.get(expected_entity_id).state == "400.0"
    assert hass.states.get(other_entity_id).state == "380.0"


@pytest.mark.usefixtures("mock_abrp_client")
async def test_update_entity_keeps_streamed_value(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A manual entity update is a no-op; the stream is the only data source."""
    assert await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    await setup_integration(hass, config_entry_with_vehicles)
    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(12000.0)),
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: POWER_ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(POWER_ENTITY_ID).state == "12000.0"
    assert "Update method not implemented" not in caplog.text
