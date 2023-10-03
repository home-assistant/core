"""The tests for Lidarr sensor platform."""
import pytest

from homeassistant.components.sensor import CONF_STATE_CLASS, SensorStateClass
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ComponentSetup

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("server", "second_folder"),
    (
        ("connection", ""),
        ("linux_connection", "_2"),
        ("windows_connection", "_2"),
        ("single_windows_connection", ""),
    ),
)
async def test_sensors(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    setup_integration: ComponentSetup,
    entity_registry_enabled_by_default: None,
    server: str,
    second_folder: str,
) -> None:
    """Test for successfully setting up the Lidarr platform."""
    request.getfixturevalue(server)
    await setup_integration()

    state = hass.states.get("sensor.mock_title_disk_space")
    assert state.state == "0.93"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "GB"
    state = hass.states.get(f"sensor.mock_title_disk_space{second_folder}")
    assert state.state == "0.93"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "GB"
    state = hass.states.get("sensor.mock_title_queue")
    assert state.state == "2"
    assert state.attributes.get("string") == "stopped"
    assert state.attributes.get("string2") == "downloading"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Albums"
    assert state.attributes.get(CONF_STATE_CLASS) == SensorStateClass.TOTAL
    state = hass.states.get("sensor.mock_title_wanted")
    assert state.state == "1"
    assert state.attributes.get("test") == "test"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Albums"
    assert state.attributes.get(CONF_STATE_CLASS) == SensorStateClass.TOTAL


@pytest.mark.parametrize(
    ("server", "second_folder", "entity_count"),
    (
        ("connection", "", 1),
        ("linux_connection", "_new", 2),
        ("windows_connection", "_new", 2),
        ("single_windows_connection", "", 1),
    ),
)
async def test_unique_id_migration(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    entity_registry_enabled_by_default: None,
    server: str,
    second_folder: str,
    entity_count: int,
) -> None:
    """Test entity registry entries get updated with the new unique id."""
    reg = er.async_get(hass)
    request.getfixturevalue(server)
    await setup_integration()
    state = hass.states.get("sensor.mock_title_disk_space")
    reg.async_update_entity(
        state.entity_id, new_unique_id=f"{config_entry.entry_id}_disk_space_"
    )
    await hass.config_entries.async_reload(config_entry.entry_id)

    entity_entries = er.async_entries_for_config_entry(reg, config_entry.entry_id)
    entities = [e for e in entity_entries if "disk_space" in e.unique_id]
    assert len(entities) == entity_count
    assert entities[0].unique_id == f"{config_entry.entry_id}_disk_space_music"
    assert (
        entities[-1].unique_id
        == f"{config_entry.entry_id}_disk_space{second_folder}_music"
    )
