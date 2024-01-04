"""Test the torque config flow."""
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.torque import config_flow
from homeassistant.components.torque.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_DATA_STEP = {
    CONF_NAME: DEFAULT_NAME,
    CONF_EMAIL: "test@example.org",
}


async def test_flow_user_init_data_success(hass: HomeAssistant) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["handler"] == "torque"
    assert result["data_schema"] == config_flow.DATA_SCHEMA

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_STEP,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].title == DEFAULT_NAME

    assert result["data"] == MOCK_DATA_STEP


MOCK_DATA_IMPORT = {
    CONF_NAME: DEFAULT_NAME,
    CONF_EMAIL: "test@example.org",
}


async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA_IMPORT,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_DATA_IMPORT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_already_configured(hass: HomeAssistant) -> None:
    """Test integration is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
