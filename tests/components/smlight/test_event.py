"""Tests for the SMLIGHT event platform."""

from unittest.mock import MagicMock

from pysmlight import Info
from pysmlight.const import Events as SmEvents
from pysmlight.sse import MessageEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_mock_event_function
from .conftest import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

MOCK_ULTIMA = Info(
    MAC="AA:BB:CC:DD:EE:FF",
    model="SLZB-Ultima3",
)

MOCK_IR_EVENT = MessageEvent(
    type="IR_CODE",
    message="IR_CODE",
    data='{"raw":"b5590d200d200c0b0c0a0c0a0d0a0c0a0d200d0a0c210c200d0a0c210c210c0a0c210c210c210c0a0c210c0a0d0a0c0a0d0a0c0a0c0b0c200d0a0c210c210c210c200d","proto":8,"addr":"0xb683","cmd":"0x000b","repeat":0,"seq":12}',
    origin="http://slzb-06.local",
    last_event_id="",
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.EVENT]


async def test_event_setup_ultima(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test event entity is created for Ultima devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    entry = await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)


async def test_event_not_created_non_ultima(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test event entity is not created for non-Ultima devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-MR1",
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.mock_title_events")
    assert state is None


@pytest.mark.freeze_time("2024-09-01 00:00:00+00:00")
async def test_ir_code_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test IR code event entity."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.mock_title_events")
    assert state.state == STATE_UNKNOWN

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.IR_CODE)
    assert event_function is not None

    event_function(MOCK_IR_EVENT)

    state = hass.states.get("event.mock_title_events")
    assert state.state == "2024-09-01T00:00:00.000+00:00"
    assert state.attributes == snapshot


async def test_ir_code_invalid_json(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test IR code event entity handles invalid json correctly."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.mock_title_events")
    assert state.state == STATE_UNKNOWN

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.IR_CODE)
    assert event_function is not None

    invalid_event = MessageEvent(
        type="ir_code",
        message="ir_code",
        data="invalid",
        origin="http://slzb-06.local",
        last_event_id="",
    )
    event_function(invalid_event)

    state = hass.states.get("event.mock_title_events")
    assert state.state == STATE_UNKNOWN
