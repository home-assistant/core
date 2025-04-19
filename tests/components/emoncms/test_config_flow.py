"""Test emoncms config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.emoncms.const import (
    CONF_ONLY_INCLUDE_FEEDID,
    DOMAIN,
    SYNC_MODE,
    SYNC_MODE_AUTO,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import (
    EMONCMS_FAILURE,
    FLOW_RESULT,
    FLOW_RESULT_SINGLE_FEED,
    SENSOR_NAME,
    YAML,
)

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_URL: "http://1.1.1.1",
    CONF_API_KEY: "my_api_key",
}

USER_INPUT_AUTO_MODE = {**USER_INPUT, SYNC_MODE: SYNC_MODE_AUTO}


@pytest.mark.parametrize(
    ("input", "feed_numbers"),
    [
        (USER_INPUT, ["1"]),
        (USER_INPUT_AUTO_MODE, FLOW_RESULT[CONF_ONLY_INCLUDE_FEEDID]),
    ],
)
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client: AsyncMock,
    input: dict,
    feed_numbers: list,
) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        input,
    )
    if input.get(SYNC_MODE) != SYNC_MODE_AUTO:
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ONLY_INCLUDE_FEEDID: feed_numbers},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SENSOR_NAME
    assert result["data"] == {**USER_INPUT, CONF_ONLY_INCLUDE_FEEDID: feed_numbers}
    assert len(mock_setup_entry.mock_calls) == 1


CONFIG_ENTRY = {
    CONF_API_KEY: "my_api_key",
    CONF_ONLY_INCLUDE_FEEDID: ["1"],
    CONF_URL: "http://1.1.1.1",
}


async def test_options_flow(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Options flow - success test."""
    await setup_integration(hass, config_entry)
    assert config_entry.options == {}
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ONLY_INCLUDE_FEEDID: ["1"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_ONLY_INCLUDE_FEEDID: ["1"],
    }


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
    assert result["errors"]["base"] == "api_error"
    assert result["description_placeholders"]["details"] == "failure"
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_unique_id_exists(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client: AsyncMock,
    config_entry_unique_id: MockConfigEntry,
) -> None:
    """Test when entry with same unique id already exists."""
    config_entry_unique_id.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
