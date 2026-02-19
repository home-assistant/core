"""Test config flow for School Holidays integration."""

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_COUNTRY, CONF_NAME, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DOMAIN, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_NAME: TEST_CALENDAR_NAME,
        CONF_COUNTRY: TEST_COUNTRY,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"

    region_input = {CONF_REGION: TEST_REGION}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=region_input
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_CALENDAR_NAME
    assert result["data"][CONF_NAME] == TEST_CALENDAR_NAME
    assert result["data"][CONF_COUNTRY] == TEST_COUNTRY
    assert result["data"][CONF_REGION] == TEST_REGION
