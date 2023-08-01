"""The test for the ping binary_sensor platform."""
from unittest.mock import patch

from homeassistant import setup
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.ping.const import NON_AVAILABLE_HOST_PING


async def test_setup_from_configuration(
    hass: HomeAssistant, mock_ping: None, mock_async_ping: None
) -> None:
    """Verify we can set up the ping sensor from the configuration.yaml."""

    await setup.async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "ping",
                "name": "test",
                "host": "127.0.0.1",
                "count": 1,
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("binary_sensor.test")


async def test_setup_from_entry(
    hass: HomeAssistant,
    mock_ping: None,
    mock_async_ping: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Verify we can set up the ping sensor from a config entry."""

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("binary_sensor.router")


async def test_enabled_by_default(
    hass: HomeAssistant,
    mock_ping: None,
    mock_async_ping: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if entity_registry_enabled_by_default is handled right imported by binary sensor."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entreg = er.async_get(hass)
    entity = entreg.async_get("binary_sensor.router")
    assert entity.disabled is False

    entity = entreg.async_get("device_tracker.router")
    assert entity.disabled is True


async def test_enabled_by_default_non_imported(
    hass: HomeAssistant,
    mock_ping: None,
    mock_async_ping: None,
    non_imported_config_entry: MockConfigEntry,
) -> None:
    """Test if entity_registry_enabled_by_default is handled right for non-imported entry."""
    await hass.config_entries.async_setup(non_imported_config_entry.entry_id)
    await hass.async_block_till_done()

    entreg = er.async_get(hass)
    entity = entreg.async_get("binary_sensor.smartphone")
    assert entity.disabled is False

    entity = entreg.async_get("device_tracker.smartphone")
    assert entity.disabled is True


async def test_extra_attributes(
    hass: HomeAssistant, mock_ping: None, mock_config_entry: MockConfigEntry
) -> None:
    """Test if missing attributes handled correctly."""

    with patch(
        "homeassistant.components.ping.ping.async_ping",
        return_value=NON_AVAILABLE_HOST_PING,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.get("binary_sensor.router").attributes) == 2
    assert hass.states.get("binary_sensor.router").attributes == {
        "device_class": "connectivity",
        "friendly_name": "Router",
    }
