"""Test Gardena Bluetooth binary sensor."""

from collections.abc import Awaitable, Callable

from gardena_bluetooth.const import Valve
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
            Valve.connected_state.uuid,
            [b"\x01", b"\x00"],
            "binary_sensor.mock_title_valve_connection",
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
    await setup_entry(hass, mock_entry, [Platform.BINARY_SENSOR])
    assert hass.states.get(entity_id) == snapshot

    for char_raw in raw[1:]:
        mock_read_char_raw[uuid] = char_raw
        await scan_step()
        assert hass.states.get(entity_id) == snapshot
