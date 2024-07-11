"""Test emoncms sensor."""

import copy
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.emoncms.const import (
    CONF_ONLY_INCLUDE_FEEDID,
    CONF_SENSOR_NAMES,
    DOMAIN,
    FEED_NAME,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_PLATFORM, CONF_URL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import FEEDS, FLOW_RESULT

from tests.common import MockConfigEntry

YAML = {
    CONF_PLATFORM: "emoncms",
    CONF_API_KEY: "my_api_key",
    CONF_ID: 1,
    CONF_URL: "http://1.1.1.1",
    CONF_ONLY_INCLUDE_FEEDID: [1, 2],
    "scan_interval": 30,
}


@pytest.fixture
def emoncms_yaml_config() -> ConfigType:
    """Mock emoncms configuration from yaml."""
    return {"sensor": YAML}


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


FLOW_RESULT_NO_FEED = copy.deepcopy(FLOW_RESULT)
FLOW_RESULT_NO_FEED[CONF_ONLY_INCLUDE_FEEDID] = None


@pytest.fixture
def config_no_feed() -> MockConfigEntry:
    """Mock emoncms config entry with no feed selected."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=FLOW_RESULT_NO_FEED[CONF_ID],
        data=FLOW_RESULT_NO_FEED,
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
    emoncms_client_no_feed: AsyncMock,
) -> None:
    """Test with no feed selected."""
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == []


FLOW_RESULT_SENSOR_NAME = copy.deepcopy(FLOW_RESULT)
FLOW_RESULT_SENSOR_NAME[CONF_SENSOR_NAMES] = {2: "energy_kitchen"}


@pytest.fixture
def config_sensor_name() -> MockConfigEntry:
    """Mock emoncms config entry with no feed selected."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=FLOW_RESULT_SENSOR_NAME[CONF_ID],
        data=FLOW_RESULT_SENSOR_NAME,
    )


async def test_sensor_name(
    hass: HomeAssistant,
    config_sensor_name: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test with no sensor name provided."""
    await setup_integration(hass, config_sensor_name)

    assert config_sensor_name.state is ConfigEntryState.LOADED
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_sensor_name.entry_id
    )
    for nb, feed in enumerate(FEEDS):
        if entity_entries[nb].unique_id.endswith("-2"):
            assert entity_entries[nb].original_name == "energy_kitchen"
        else:
            assert entity_entries[nb].original_name == f"EmonCMS {feed[FEED_NAME]}"
