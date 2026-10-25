"""The tests for the folder sensor."""

from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.folder.const import CONF_FILTER, CONF_FOLDER_PATHS, DOMAIN
from homeassistant.components.folder.sensor import SCAN_INTERVAL
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import TEST_FILE_CONTENT, TEST_FILE_NAME

ENTITY_ID = "sensor.test_folder"


async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    folder_path: str,
) -> None:
    """Test the sensor reports the files in the folder."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "0.0"
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT
    assert state.attributes["path"] == f"{folder_path}/"
    assert state.attributes["filter"] == "*"
    assert state.attributes["number_of_files"] == 1
    assert state.attributes["bytes"] == len(TEST_FILE_CONTENT)
    assert state.attributes["file_list"] == [f"{folder_path}/{TEST_FILE_NAME}"]

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry
    assert entity_entry.unique_id == mock_config_entry.entry_id


async def test_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    folder_path: str,
) -> None:
    """Test the sensor picks up new files on the next update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    Path(folder_path, "second.txt").write_text("more data", encoding="utf8")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes["number_of_files"] == 2
    assert state.attributes["bytes"] == len(TEST_FILE_CONTENT) + len("more data")


async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, folder_path: str
) -> None:
    """Test the YAML platform is imported and reported as deprecated."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_FOLDER_PATHS: folder_path}},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].options == {CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*"}
    assert hass.states.get(ENTITY_ID)
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    folder_path: str,
) -> None:
    """Test no second entry is created, but the deprecation issue still is."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_FOLDER_PATHS: folder_path}},
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_not_allowed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, folder_path: str
) -> None:
    """Test a failed YAML import raises a repair issue explaining why."""
    hass.config.allowlist_external_dirs = set()

    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_FOLDER_PATHS: folder_path}},
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_not_allowed_dir_{folder_path}"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("folder_path")
async def test_yaml_invalid_path(hass: HomeAssistant) -> None:
    """Test a YAML path that is not a directory is rejected by the schema."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_FOLDER_PATHS: "invalid_path"}},
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert not hass.states.async_entity_ids(SENSOR_DOMAIN)
