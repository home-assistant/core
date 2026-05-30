"""Test the Amcrest integration init."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_CONFIG_ENTRY_TITLE, setup_mock_amcrest_checker

from tests.common import MockConfigEntry


async def test_setup_entry_loads_platforms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry setup loads all platforms and stores runtime data."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.amcrest.AmcrestChecker") as mock_checker,
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        setup_mock_amcrest_checker(mock_checker)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.device is not None
    assert mock_config_entry.runtime_data.stop_event is not None

    entity_ids = hass.states.async_entity_ids()
    title_slug = TEST_CONFIG_ENTRY_TITLE.lower().replace(" ", "_")
    assert f"binary_sensor.{title_slug}_audio_detected" in entity_ids
    assert f"binary_sensor.{title_slug}_motion_detected" in entity_ids
    assert f"binary_sensor.{title_slug}_crossline_detected" in entity_ids
    assert f"binary_sensor.{title_slug}_online" in entity_ids
    assert f"camera.{title_slug}" in entity_ids
    assert f"sensor.{title_slug}_ptz_preset" in entity_ids
    assert f"sensor.{title_slug}_sd_used" in entity_ids
    assert f"switch.{title_slug}_privacy_mode" in entity_ids


async def test_unload_entry(
    hass: HomeAssistant,
    loaded_config_entry: MockConfigEntry,
) -> None:
    """Test config entry unload sets stop_event and unloads platforms."""
    stop_event = loaded_config_entry.runtime_data.stop_event

    assert await hass.config_entries.async_unload(loaded_config_entry.entry_id)
    await hass.async_block_till_done()

    assert stop_event.is_set()
    assert loaded_config_entry.state is ConfigEntryState.NOT_LOADED
