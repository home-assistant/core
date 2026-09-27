"""The tests for the WSDOT platform."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.wsdot.const import CONF_TRAVEL_TIMES, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_PLATFORM,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, snapshot_platform


async def test_travel_sensor_details(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the wsdot Travel Time sensor details."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_travel_sensor_platform_setup(
    hass: HomeAssistant, mock_travel_time: AsyncMock, issue_registry: ir.IssueRegistry
) -> None:
    """Test the wsdot Travel Time sensor still supports setup from platform config."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            Platform.SENSOR: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_API_KEY: "foo",
                    CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I90 EB"}],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    entry = next(iter(hass.config_entries.async_entries(DOMAIN)), None)
    assert entry is not None
    assert entry.data[CONF_API_KEY] == "foo"
    assert len(entry.subentries) == 1
    assert len(issue_registry.issues) == 1


async def test_travel_sensor_platform_setup_bad_routes(
    hass: HomeAssistant, mock_travel_time: AsyncMock, issue_registry: ir.IssueRegistry
) -> None:
    """Test the wsdot Travel Time sensor platform upgrade skips unknown route ids."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            Platform.SENSOR: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_API_KEY: "foo",
                    CONF_TRAVEL_TIMES: [{CONF_ID: 4096, CONF_NAME: "Mars Expressway"}],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entry = next(iter(hass.config_entries.async_entries(DOMAIN)), None)
    assert entry is None
    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_travel_time_id"
    )
    assert issue
