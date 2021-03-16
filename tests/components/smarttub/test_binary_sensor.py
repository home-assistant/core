"""Test the SmartTub binary sensor platform."""
from datetime import date, timedelta

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


async def test_reminders(spa, setup_entry, hass):
    """Test the reminder sensor."""

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_myfilter_reminder"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert date.fromisoformat(state.attributes["date"]) <= date.today() + timedelta(
        days=2
    )
    assert state.attributes["snoozed"] is False
