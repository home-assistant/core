"""Test Gardena Bluetooth sensor."""
from collections.abc import Awaitable, Callable

from gardena_bluetooth.const import Battery, Sensor, Valve
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_entry

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("uuid", "raw", "entity_id"),
    [
        (
            Battery.battery_level.uuid,
            [Battery.battery_level.encode(100), Battery.battery_level.encode(10)],
            "sensor.mock_title_battery",
        ),
        (
            Valve.remaining_open_time.uuid,
            [
                Valve.remaining_open_time.encode(100),
                Valve.remaining_open_time.encode(10),
                Valve.remaining_open_time.encode(0),
            ],
            "sensor.mock_title_valve_closing",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    scan_step: Callable[[], Awaitable[None]],
    uuid: str,
    raw: list[bytes],
    entity_id: str,
) -> None:
    """Test setup creates expected entities."""

    mock_read_char_raw[uuid] = raw[0]
    await setup_entry(hass, mock_entry, [Platform.SENSOR])
    assert hass.states.get(entity_id) == snapshot

    for char_raw in raw[1:]:
        mock_read_char_raw[uuid] = char_raw
        await scan_step()
        assert hass.states.get(entity_id) == snapshot


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
