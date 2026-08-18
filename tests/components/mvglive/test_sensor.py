"""Test the mvglive sensor platform."""

import pytest

from homeassistant.components.mvglive.const import CONF_ENABLE_MESSAGES
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mvg_api")
async def test_messages_sensor_created_by_default(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the messages sensor is created when enabled (the default)."""
    await setup_integration(hass, config_entry)

    departures = hass.states.get("sensor.hauptbahnhof")
    assert departures is not None
    assert "messages" not in departures.attributes

    messages = hass.states.get("sensor.hauptbahnhof_messages")
    assert messages is not None
    assert messages.state == "0"


@pytest.mark.usefixtures("mvg_api")
async def test_messages_sensor_disabled_via_options(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the messages sensor is not created when disabled via options."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ENABLE_MESSAGES: False}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.hauptbahnhof_messages") is None
