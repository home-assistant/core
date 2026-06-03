"""Tests for the openSenseMap integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from opensensemap_api.exceptions import OpenSenseMapError
import pytest

from homeassistant.components.opensensemap.const import CONF_STATION_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import TEST_STATION_ID

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_opensensemap_api")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("air_quality.test_station")
    assert state is not None
    assert state.attributes["particulate_matter_2_5"] == 5.42
    assert state.attributes["particulate_matter_10"] == 9.17


async def test_async_update_failure_marks_unavailable(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an API error after setup marks the entity as unavailable."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("air_quality.test_station").state != "unavailable"

    mock_opensensemap_api.get_data.side_effect = OpenSenseMapError
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("air_quality.test_station").state == "unavailable"

    mock_opensensemap_api.get_data.side_effect = None
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("air_quality.test_station").state != "unavailable"


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry stays in SETUP_RETRY if the API is unreachable."""
    mock_opensensemap_api.get_data.side_effect = OpenSenseMapError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_opensensemap_api")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_opensensemap_api")
async def test_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing a YAML configuration creates a config entry and deprecation issue."""
    config = {
        "air_quality": [{"platform": "opensensemap", CONF_STATION_ID: TEST_STATION_ID}]
    }
    assert await async_setup_component(hass, "air_quality", config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == TEST_STATION_ID

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_station"
    )


async def test_yaml_import_cannot_connect(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_opensensemap_api: AsyncMock,
) -> None:
    """Test a YAML import that fails with a connection error creates an issue."""
    mock_opensensemap_api.get_data.side_effect = OpenSenseMapError

    config = {
        "air_quality": [{"platform": "opensensemap", CONF_STATION_ID: TEST_STATION_ID}]
    }
    assert await async_setup_component(hass, "air_quality", config)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_invalid_station(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_opensensemap_api: AsyncMock,
) -> None:
    """Test a YAML import that fails with an invalid station creates an issue."""
    mock_opensensemap_api.data = {}

    config = {
        "air_quality": [{"platform": "opensensemap", CONF_STATION_ID: TEST_STATION_ID}]
    }
    assert await async_setup_component(hass, "air_quality", config)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_station"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_opensensemap_api")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test importing YAML when a config entry already exists still creates the deprecation issue."""
    mock_config_entry.add_to_hass(hass)

    config = {
        "air_quality": [{"platform": "opensensemap", CONF_STATION_ID: TEST_STATION_ID}]
    }
    assert await async_setup_component(hass, "air_quality", config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].entry_id == mock_config_entry.entry_id
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_station"
    )
