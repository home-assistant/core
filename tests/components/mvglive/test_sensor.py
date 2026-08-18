"""Test the mvglive sensor platform."""

import pytest

from homeassistant.components.mvglive.const import CONF_ENABLE_MESSAGES
from homeassistant.components.mvglive.sensor import PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


def test_platform_schema_accepts_deprecated_directions() -> None:
    """Test that a legacy `directions` key still validates so the YAML can be imported.

    `directions` was deprecated in the old platform-only setup; existing
    users may still have it in `configuration.yaml`. It must not cause
    schema validation to fail, or the automatic YAML-to-config-entry import
    would break for them.
    """
    PLATFORM_SCHEMA(
        {
            "platform": "mvglive",
            "nextdeparture": [{"station": "Hauptbahnhof", "directions": "Feldmoching"}],
        }
    )


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
