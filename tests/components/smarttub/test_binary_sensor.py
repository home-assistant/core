"""Test the SmartTub binary sensor platform."""
from datetime import datetime
from unittest.mock import create_autospec

import pytest
import smarttub

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    STATE_OFF,
    STATE_ON,
)


async def test_binary_sensors(spa, setup_entry, hass):
    """Test simple binary sensors."""

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_online"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get("device_class") == DEVICE_CLASS_CONNECTIVITY

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_error"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_reminders(spa, setup_entry, hass):
    """Test the reminder sensor."""

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_myfilter_reminder"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["snoozed"] is False


@pytest.fixture
def mock_error(spa):
    """Mock error."""
    error = create_autospec(smarttub.SpaError, instance=True)
    error.code = 11
    error.title = "Flow Switch Stuck Open"
    error.description = None
    error.active = True
    error.created_at = datetime.now()
    error.updated_at = datetime.now()
    error.error_type = "TUB_ERROR"
    return error


@pytest.mark.parametrize(
    "errors",
    [[], [mock_error]],
)
async def test_errors(spa, hass, config_entry, errors):
    """Test the error sensor."""

    spa.get_errors.return_value = errors

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_error"
    state = hass.states.get(entity_id)

    if len(errors) == 0:
        assert state is not None
        assert state.state == STATE_OFF
    else:
        assert state.state == STATE_ON
        assert state.attributes["error_code"] == 11
