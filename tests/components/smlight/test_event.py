"""Tests for the SMLIGHT event platform."""

from unittest.mock import MagicMock

from pysmlight.const import Events as SmEvents
from pysmlight.sse import MessageEvent
import pytest

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from . import get_mock_event_function
from .conftest import setup_integration

from tests.common import MockConfigEntry

MOCK_REBOOT_EVENT = MessageEvent(
    type="reboot",
    message="reboot",
    data='{"reason": 3, "epoch": 1634020800}',
    origin="http://slzb-06.local",
    last_event_id="",
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.EVENT]


@pytest.mark.freeze_time("2024-09-01 00:00:00+00:00")
async def test_reboot_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test event entity."""

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.mock_title_event")
    assert state.state == STATE_UNKNOWN

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.REBOOT)
    assert event_function is not None

    event_function(MOCK_REBOOT_EVENT)

    state = hass.states.get("event.mock_title_event")
    assert state.state == "2024-09-01T00:00:00.000+00:00"
    assert state.attributes == {
        "event_types": ["core-reboot"],
        "event_type": "core-reboot",
        "reason": "ESP_RST_SW",
        "epoch": 1634020800,
        "friendly_name": "Mock Title Event",
    }
