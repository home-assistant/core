"""Test emoncms sensor."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.emoncms.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import EMONCMS_FAILURE, get_feed

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_deprecated_yaml(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    emoncms_yaml_config: ConfigType,
    emoncms_client: AsyncMock,
) -> None:
    """Test an issue is created when we import from yaml config."""

    await async_setup_component(hass, SENSOR_DOMAIN, emoncms_yaml_config)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN, issue_id=f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_with_template(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    emoncms_yaml_config_with_template: ConfigType,
    emoncms_client: AsyncMock,
) -> None:
    """Test an issue is created when we import a yaml config with a value_template parameter."""

    await async_setup_component(hass, SENSOR_DOMAIN, emoncms_yaml_config_with_template)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"remove_value_template_{DOMAIN}"
    )


async def test_yaml_no_include_only_feed_id(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    emoncms_yaml_config_no_include_only_feed_id: ConfigType,
    emoncms_client: AsyncMock,
) -> None:
    """Test an issue is created when we import a yaml config without a include_only_feed_id parameter."""

    await async_setup_component(
        hass, SENSOR_DOMAIN, emoncms_yaml_config_no_include_only_feed_id
    )
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"missing_include_only_feed_id_{DOMAIN}"
    )


async def test_no_feed_selected(
    hass: HomeAssistant,
    config_no_feed: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test with no feed selected."""
    await setup_integration(hass, config_no_feed)

    assert config_no_feed.state is ConfigEntryState.LOADED
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_no_feed.entry_id
    )
    assert entity_entries == []


async def test_no_feed_broadcast(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test with no feed broadcasted."""
    emoncms_client.async_request.return_value = {"success": True, "message": []}
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == []


async def test_coordinator_update(
    hass: HomeAssistant,
    config_single_feed: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    emoncms_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update."""
    emoncms_client.async_request.return_value = {
        "success": True,
        "message": [get_feed(1, unit="°C")],
    }
    await setup_integration(hass, config_single_feed)

    await snapshot_platform(
        hass, entity_registry, snapshot, config_single_feed.entry_id
    )

    async def skip_time() -> None:
        freezer.tick(60)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    emoncms_client.async_request.return_value = {
        "success": True,
        "message": [get_feed(1, unit="°C", value=24.04, timestamp=1665509670)],
    }

    await skip_time()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_single_feed.entry_id
    )

    for entity_entry in entity_entries:
        state = hass.states.get(entity_entry.entity_id)
        assert state.attributes["LastUpdated"] == 1665509670
        assert state.state == "24.04"

    emoncms_client.async_request.return_value = EMONCMS_FAILURE

    await skip_time()

    assert f"Error fetching {DOMAIN}_coordinator data" in caplog.text
