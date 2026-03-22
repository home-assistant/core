"""Test Gardena Bluetooth sensor."""

from collections.abc import Awaitable, Callable
from datetime import datetime

from gardena_bluetooth.const import (
    AquaContourBattery,
    AquaContourErrorCode,
    Battery,
    EventHistory,
    FlowStatistics,
    Sensor,
    Spray,
    Valve,
)
from gardena_bluetooth.parse import ErrorData
from habluetooth import BluetoothServiceInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AQUA_CONTOUR_SERVICE_INFO, WATER_TIMER_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("service_info", "uuid", "raw", "entity_id"),
    [
        pytest.param(
            WATER_TIMER_SERVICE_INFO,
            Battery.battery_level.uuid,
            [Battery.battery_level.encode(100), Battery.battery_level.encode(10)],
            "sensor.mock_title_battery",
            id="standard_sensor",
        ),
        pytest.param(
            WATER_TIMER_SERVICE_INFO,
            Valve.remaining_open_time.uuid,
            [
                Valve.remaining_open_time.encode(100),
                Valve.remaining_open_time.encode(10),
                Valve.remaining_open_time.encode(0),
            ],
            "sensor.mock_title_valve_closing",
            id="valve_sensor",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
    service_info: BluetoothServiceInfo,
    uuid: str,
    raw: list[bytes],
    entity_id: str,
) -> None:
    """Test setup creates expected entities."""
    mock_read_char_raw[uuid] = raw[0]
    await setup_entry(hass, platforms=[Platform.SENSOR], service_info=service_info)
    assert hass.states.get(entity_id) == snapshot

    for char_raw in raw[1:]:
        mock_read_char_raw[uuid] = char_raw
        await scan_step()
        assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    ("service_info", "raw"),
    [
        pytest.param(
            WATER_TIMER_SERVICE_INFO,
            {
                Battery.battery_level.uuid: Battery.battery_level.encode(100),
                Valve.remaining_open_time.uuid: Valve.remaining_open_time.encode(10),
            },
            id="timer",
        ),
        pytest.param(
            AQUA_CONTOUR_SERVICE_INFO,
            {
                AquaContourBattery.battery_level.uuid: AquaContourBattery.battery_level.encode(
                    100
                ),
                FlowStatistics.overall.uuid: FlowStatistics.overall.encode(111),
                FlowStatistics.current.uuid: FlowStatistics.overall.encode(222),
                Spray.current_distance.uuid: Spray.current_distance.encode(333),
                Spray.current_sector.uuid: Spray.current_sector.encode(2),
                EventHistory.error.uuid: EventHistory.error.encode(
                    ErrorData(
                        1, 1, datetime(2000, 1, 1), AquaContourErrorCode.FLASH_ERROR
                    )
                ),
            },
            id="aqua_contour",
        ),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_read_char_raw: dict[str, bytes],
    service_info: BluetoothServiceInfo,
    raw: dict[str, bytes],
) -> None:
    """Test setup creates expected entities."""
    mock_read_char_raw.update(raw)
    mock_entry = await setup_entry(
        hass, platforms=[Platform.SENSOR], service_info=service_info
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_connected_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Verify that a connectivity error makes all entities unavailable."""

    mock_read_char_raw[Sensor.connected_state.uuid] = Sensor.connected_state.encode(
        False
    )
    mock_read_char_raw[Sensor.battery_level.uuid] = Sensor.battery_level.encode(45)

    await setup_entry(hass, mock_entry, [Platform.SENSOR])
    assert hass.states.get("sensor.mock_title_sensor_battery") == snapshot

    mock_read_char_raw[Sensor.connected_state.uuid] = Sensor.connected_state.encode(
        True
    )

    await scan_step()
    assert hass.states.get("sensor.mock_title_sensor_battery") == snapshot
