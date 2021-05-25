"""Test the SmartTub binary sensor platform."""
from homeassistant.components.binary_sensor import STATE_OFF


async def test_binary_sensors(spa, setup_entry, hass):
    """Test simple binary sensors."""

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_online"
    state = hass.states.get(entity_id)
    # disabled by default
    assert state is None


async def test_reminders(spa, setup_entry, hass):
    """Test the reminder sensor."""

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_myfilter_reminder"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["snoozed"] is False


async def test_snooze(spa, setup_entry, hass):
    """Test snoozing a reminder."""

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_myfilter_reminder"
    reminder = spa.get_reminders.return_value[0]
    days = 30

    await hass.services.async_call(
        "smarttub",
        "snooze_reminder",
        {
            "entity_id": entity_id,
            "days": 30,
        },
        blocking=True,
    )

    reminder.snooze.assert_called_with(days)
