"""Test Gardena Bluetooth sensor."""


from unittest.mock import Mock, call

from gardena_bluetooth.const import Valve
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

from . import setup_entry

from tests.common import MockConfigEntry


@pytest.fixture
def mock_switch_chars(mock_read_char_raw):
    """Mock data on device."""
    mock_read_char_raw[Valve.state.uuid] = b"\x00"
    mock_read_char_raw[
        Valve.remaining_open_time.uuid
    ] = Valve.remaining_open_time.encode(0)
    mock_read_char_raw[
        Valve.manual_watering_time.uuid
    ] = Valve.manual_watering_time.encode(1000)
    return mock_read_char_raw


async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_switch_chars: dict[str, bytes],
) -> None:
    """Test setup creates expected entities."""

    entity_id = "switch.mock_title_open"
    coordinator = await setup_entry(hass, mock_entry, [Platform.SWITCH])
    assert hass.states.get(entity_id) == snapshot

    mock_switch_chars[Valve.state.uuid] = b"\x01"
    await coordinator.async_refresh()
    assert hass.states.get(entity_id) == snapshot


async def test_switching(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_switch_chars: dict[str, bytes],
) -> None:
    """Test switching makes correct calls."""

    entity_id = "switch.mock_title_open"
    await setup_entry(hass, mock_entry, [Platform.SWITCH])
    assert hass.states.get(entity_id)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_client.write_char.mock_calls == [
        call(Valve.remaining_open_time, 1000),
        call(Valve.remaining_open_time, 0),
    ]
