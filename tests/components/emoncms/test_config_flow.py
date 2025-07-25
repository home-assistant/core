"""Test emoncms config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.emoncms.const import (
    CONF_ONLY_INCLUDE_FEEDID,
    DOMAIN,
    SYNC_MODE,
    SYNC_MODE_AUTO,
    SYNC_MODE_MANUAL,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import EMONCMS_FAILURE, FLOW_RESULT, SENSOR_NAME, UNIQUE_ID

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_URL: "http://1.1.1.1",
    CONF_API_KEY: "my_api_key",
}


@pytest.mark.parametrize(
    ("url", "api_key"),
    [
        (USER_INPUT[CONF_URL], "regenerated_api_key"),
        ("http://1.1.1.2", USER_INPUT[CONF_API_KEY]),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
    url: str,
    api_key: str,
) -> None:
    """Test reconfigure flow."""
    new_input = {
        CONF_URL: url,
        CONF_API_KEY: api_key,
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=SENSOR_NAME,
        data=new_input,
        unique_id=UNIQUE_ID,
    )
    await setup_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_input,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == new_input


async def test_reconfigure_api_error(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
) -> None:
    """Test reconfigure flow with API error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=SENSOR_NAME,
        data=USER_INPUT,
        unique_id=UNIQUE_ID,
    )
    await setup_integration(hass, config_entry)
    emoncms_client.async_request.return_value = EMONCMS_FAILURE
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_error"}
    assert result["description_placeholders"]["details"] == "failure"
    assert result["step_id"] == "reconfigure"


async def test_user_flow_failure(
    hass: HomeAssistant, emoncms_client: AsyncMock
) -> None:
    """Test emoncms failure when adding a new entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    emoncms_client.async_request.return_value = EMONCMS_FAILURE
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["errors"]["base"] == "api_error"
    assert result["description_placeholders"]["details"] == "failure"
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow_manual_mode(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, emoncms_client: AsyncMock
) -> None:
    """Test we get the user forms and the entry in manual mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, SYNC_MODE: SYNC_MODE_MANUAL},
    )

    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ONLY_INCLUDE_FEEDID: ["1"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SENSOR_NAME
    assert result["data"] == {**USER_INPUT, CONF_ONLY_INCLUDE_FEEDID: ["1"]}
    # assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_auto_mode(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, emoncms_client: AsyncMock
) -> None:
    """Test we get the user form and the entry in automatic mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, SYNC_MODE: SYNC_MODE_AUTO},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SENSOR_NAME
    assert result["data"] == {
        **USER_INPUT,
        CONF_ONLY_INCLUDE_FEEDID: FLOW_RESULT[CONF_ONLY_INCLUDE_FEEDID],
    }
    assert len(mock_setup_entry.mock_calls) == 1


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
    emoncms_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Options flow - test failure."""
    await setup_integration(hass, config_entry)
    emoncms_client.async_request.return_value = EMONCMS_FAILURE
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
