"""Test the Amcrest integration init."""

from unittest.mock import patch

from homeassistant.components.amcrest.const import RESOLUTION_LIST
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_CONFIG_ENTRY_TITLE, TEST_SERIAL, setup_mock_amcrest_checker

from tests.common import MockConfigEntry


async def _async_update_entity(
    hass: HomeAssistant, domain: str, entity_id: str
) -> None:
    """Trigger an entity update."""
    entity = hass.data[domain].get_entity(entity_id)
    assert entity is not None
    await entity.async_update()
    await hass.async_block_till_done()


async def test_setup_entry_loads_platforms(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry setup loads all platforms and stores runtime data."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.amcrest.AmcrestChecker") as mock_checker:
        setup_mock_amcrest_checker(mock_checker)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.device is not None
    assert mock_config_entry.runtime_data.event_monitor_task is not None
    assert not mock_config_entry.runtime_data.event_monitor_task.done()

    entity_ids = hass.states.async_entity_ids()
    title_slug = TEST_CONFIG_ENTRY_TITLE.lower().replace(" ", "_")
    assert f"binary_sensor.{title_slug}_audio_detected" in entity_ids
    assert f"binary_sensor.{title_slug}_motion_detected" in entity_ids
    assert f"binary_sensor.{title_slug}_crossline_detected" in entity_ids
    assert f"binary_sensor.{title_slug}_online" in entity_ids
    assert f"camera.{title_slug}" in entity_ids
    assert f"switch.{title_slug}_privacy_mode" in entity_ids
    assert entity_registry.async_get(f"sensor.{title_slug}_ptz_preset") is not None
    assert entity_registry.async_get(f"sensor.{title_slug}_sd_used") is not None


async def test_unload_entry(
    hass: HomeAssistant,
    loaded_config_entry: MockConfigEntry,
) -> None:
    """Test config entry unload unloads platforms."""
    monitor_task = loaded_config_entry.runtime_data.event_monitor_task
    assert monitor_task is not None
    assert not monitor_task.done()

    assert await hass.config_entries.async_unload(loaded_config_entry.entry_id)
    await hass.async_block_till_done()

    assert loaded_config_entry.state is ConfigEntryState.NOT_LOADED
    assert monitor_task.done()


async def test_setup_entry_starts_event_monitor_task(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry setup starts the event monitor background task."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.amcrest.AmcrestChecker") as mock_checker:
        setup_mock_amcrest_checker(mock_checker)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    task = mock_config_entry.runtime_data.event_monitor_task
    assert task is not None
    assert not task.done()


async def test_reload_does_not_duplicate_monitors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reload cancels the previous monitor before starting a new one."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.amcrest.AmcrestChecker") as mock_checker:
        setup_mock_amcrest_checker(mock_checker)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        first_task = mock_config_entry.runtime_data.event_monitor_task
        assert first_task is not None
        assert not first_task.done()

        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    second_task = mock_config_entry.runtime_data.event_monitor_task
    assert second_task is not None
    assert first_task.done()
    assert not second_task.done()
    assert second_task is not first_task


async def test_binary_sensor_assigns_unique_id_on_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    loaded_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensors lazily assign unique_id during update."""
    title_slug = TEST_CONFIG_ENTRY_TITLE.lower().replace(" ", "_")
    entity_id = f"binary_sensor.{title_slug}_motion_detected"

    await _async_update_entity(hass, "binary_sensor", entity_id)

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == f"{TEST_SERIAL}-motion_detected-0"


async def test_camera_assigns_unique_id_on_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    loaded_config_entry: MockConfigEntry,
) -> None:
    """Test camera lazily assigns unique_id during update."""
    title_slug = TEST_CONFIG_ENTRY_TITLE.lower().replace(" ", "_")
    entity_id = f"camera.{title_slug}"

    await _async_update_entity(hass, "camera", entity_id)

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == f"{TEST_SERIAL}-{RESOLUTION_LIST['high']}-0"
