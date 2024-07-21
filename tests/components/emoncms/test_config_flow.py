"""Test emoncms config flow."""

import copy
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.emoncms.const import (
    CONF_EXCLUDE_FEEDID,
    CONF_ONLY_INCLUDE_FEEDID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_PLATFORM,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import FAILURE_MESSAGE, FLOW_RESULT, SENSOR_NAME

from tests.common import MockConfigEntry

YAML = {
    CONF_PLATFORM: "emoncms",
    CONF_API_KEY: "my_api_key",
    CONF_ID: 1,
    CONF_URL: "http://1.1.1.1",
}


async def flow_import(hass: HomeAssistant, yaml: dict[str, Any]) -> ConfigFlowResult:
    """Import of a yaml config."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml,
    )


async def test_flow_import_all_feeds(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
) -> None:
    """YAML import of all feeds - success test."""
    result = await flow_import(hass, YAML)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SENSOR_NAME
    assert result["data"] == FLOW_RESULT


YAML_INCL_FEED = copy.deepcopy(YAML)
YAML_INCL_FEED[CONF_ONLY_INCLUDE_FEEDID] = [2]

FLOW_RESULT_INCL_FEED = copy.deepcopy(FLOW_RESULT)
FLOW_RESULT_INCL_FEED[CONF_ONLY_INCLUDE_FEEDID] = ["2"]
FLOW_RESULT_INCL_FEED[CONF_EXCLUDE_FEEDID] = None


async def test_flow_import_include_feeds(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
) -> None:
    """YAML import with included feed - success test."""
    result = await flow_import(hass, YAML_INCL_FEED)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SENSOR_NAME
    assert result["data"] == FLOW_RESULT_INCL_FEED


YAML_EXCL_FEED = copy.deepcopy(YAML)
YAML_EXCL_FEED[CONF_EXCLUDE_FEEDID] = [2]

FLOW_RESULT_EXCL_FEED = copy.deepcopy(FLOW_RESULT)
FLOW_RESULT_EXCL_FEED[CONF_ONLY_INCLUDE_FEEDID] = None
FLOW_RESULT_EXCL_FEED[CONF_EXCLUDE_FEEDID] = ["2"]


async def test_flow_import_exclude_feed(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
) -> None:
    """YAML import with excluded feed - success test."""
    result = await flow_import(hass, YAML_EXCL_FEED)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SENSOR_NAME
    assert result["data"] == FLOW_RESULT_EXCL_FEED


async def test_flow_import_failure(
    hass: HomeAssistant,
    emoncms_client_failure: AsyncMock,
) -> None:
    """YAML import - failure test."""
    result = await flow_import(hass, YAML)
    assert result["type"] == FlowResultType.ABORT


async def options_flow(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    user_input: dict[str, Any],
    final: dict[str, Any],
) -> None:
    """Options flow generic success test."""
    await setup_integration(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == final


USER_INPUT = {
    CONF_URL: "http://1.1.1.1",
    CONF_API_KEY: "my_api_key",
    CONF_ONLY_INCLUDE_FEEDID: ["1"],
}

CONFIG_ENTRY = {
    CONF_API_KEY: "my_api_key",
    CONF_ONLY_INCLUDE_FEEDID: ["1"],
    CONF_URL: "http://1.1.1.1",
    CONF_EXCLUDE_FEEDID: None,
    CONF_UNIT_OF_MEASUREMENT: None,
}

USER_INPUT_2 = {
    CONF_URL: "http://1.1.1.1",
    CONF_API_KEY: "my_api_key",
    CONF_ONLY_INCLUDE_FEEDID: ["1", "2"],
}

CONFIG_ENTRY_2 = copy.deepcopy(CONFIG_ENTRY)
CONFIG_ENTRY_2[CONF_ONLY_INCLUDE_FEEDID] = ["1", "2"]


@pytest.fixture
def config_entry_excl_feed() -> MockConfigEntry:
    """Mock emoncms config entry with excluded fields."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=SENSOR_NAME,
        data=FLOW_RESULT_EXCL_FEED,
    )


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client: AsyncMock,
    config_entry: MockConfigEntry,
    config_entry_excl_feed: MockConfigEntry,
) -> None:
    """Options flow - success test."""
    await options_flow(hass, config_entry, USER_INPUT, CONFIG_ENTRY)
    await options_flow(hass, config_entry_excl_feed, USER_INPUT_2, CONFIG_ENTRY_2)


async def test_options_flow_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client_failure: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Options flow - test failure."""
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result["errors"]["base"] == FAILURE_MESSAGE
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
