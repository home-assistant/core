"""Test Gardena Bluetooth sensor."""


from unittest.mock import Mock, call

from gardena_bluetooth.const import Reset
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    Platform,
)
from homeassistant.core import HomeAssistant

from . import setup_entry

from tests.common import MockConfigEntry


@pytest.fixture
def mock_switch_chars(mock_read_char_raw):
    """Mock data on device."""
    mock_read_char_raw[Reset.factory_reset.uuid] = b"\x00"
    return mock_read_char_raw


async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_switch_chars: dict[str, bytes],
) -> None:
    """Test setup creates expected entities."""

    entity_id = "button.mock_title_factory_reset"
    coordinator = await setup_entry(hass, mock_entry, [Platform.BUTTON])
    assert hass.states.get(entity_id) == snapshot

    mock_switch_chars[Reset.factory_reset.uuid] = b"\x01"
    await coordinator.async_refresh()
    assert hass.states.get(entity_id) == snapshot


async def test_switching(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_switch_chars: dict[str, bytes],
) -> None:
    """Test switching makes correct calls."""

    entity_id = "button.mock_title_factory_reset"
    await setup_entry(hass, mock_entry, [Platform.BUTTON])
    assert hass.states.get(entity_id)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_client.write_char.mock_calls == [
        call(Reset.factory_reset, True),
    ]
