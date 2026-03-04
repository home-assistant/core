"""Test Smarla entities."""

import logging
from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration, update_property_listeners

from tests.common import MockConfigEntry

TEST_ENTITY_ID = "switch.smarla"


async def test_entity_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
) -> None:
    """Test entity state when device becomes unavailable/available."""
    assert await setup_integration(hass, mock_config_entry)

    # Initially available
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Simulate device becoming unavailable
    mock_federwiege.available = False
    await update_property_listeners(mock_federwiege)
    await hass.async_block_till_done()

    # Verify state reflects unavailable
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate device becoming available again
    mock_federwiege.available = True
    await update_property_listeners(mock_federwiege)
    await hass.async_block_till_done()

    # Verify state reflects available again
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_entity_unavailable_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    mock_federwiege: MagicMock,
) -> None:
    """Test logging when device becomes unavailable/available."""
    assert await setup_integration(hass, mock_config_entry)

    caplog.set_level(logging.INFO)
    caplog.clear()

    # Verify that log exists when device becomes unavailable
    mock_federwiege.available = False
    await update_property_listeners(mock_federwiege)
    await hass.async_block_till_done()
    assert "is unavailable" in caplog.text

    # Verify that we only log once
    caplog.clear()
    await update_property_listeners(mock_federwiege)
    await hass.async_block_till_done()
    assert "is unavailable" not in caplog.text

    # Verify that log exists when device comes back online
    mock_federwiege.available = True
    await update_property_listeners(mock_federwiege)
    await hass.async_block_till_done()
    assert "back online" in caplog.text

    # Verify that we only log once
    caplog.clear()
    await update_property_listeners(mock_federwiege)
    await hass.async_block_till_done()
    assert "back online" not in caplog.text
