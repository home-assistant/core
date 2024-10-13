"""Test emoncms config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.emoncms.const import CONF_ONLY_INCLUDE_FEEDID, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import EMONCMS_FAILURE, FLOW_RESULT_SINGLE_FEED, SENSOR_NAME, YAML

from tests.common import MockConfigEntry


async def test_flow_import_include_feeds(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client: AsyncMock,
) -> None:
    """YAML import with included feed - success test."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SENSOR_NAME
    assert result["data"] == FLOW_RESULT_SINGLE_FEED


async def test_flow_import_failure(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
) -> None:
    """YAML import - failure test."""
    emoncms_client.async_request.return_value = EMONCMS_FAILURE
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == EMONCMS_FAILURE["message"]


async def test_flow_import_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    emoncms_client: AsyncMock,
) -> None:
    """Test we abort import data set when entry is already configured."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


USER_INPUT = {
    CONF_URL: "http://1.1.1.1",
    CONF_API_KEY: "my_api_key",
}


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client: AsyncMock,
) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ONLY_INCLUDE_FEEDID: ["1"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SENSOR_NAME
    assert result["data"] == {**USER_INPUT, CONF_ONLY_INCLUDE_FEEDID: ["1"]}
    assert len(mock_setup_entry.mock_calls) == 1


USER_OPTIONS = {
    CONF_ONLY_INCLUDE_FEEDID: ["1"],
}

CONFIG_ENTRY = {
    CONF_API_KEY: "my_api_key",
    CONF_ONLY_INCLUDE_FEEDID: ["1"],
    CONF_URL: "http://1.1.1.1",
}


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Options flow - success test."""
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=USER_OPTIONS,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == CONFIG_ENTRY
    assert config_entry.options == CONFIG_ENTRY


async def test_options_flow_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Options flow - test failure."""
    emoncms_client.async_request.return_value = EMONCMS_FAILURE
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result["errors"]["base"] == "failure"
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
