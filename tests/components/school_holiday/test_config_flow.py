"""Test config flow for School Holiday integration."""

import pytest

from homeassistant import config_entries
from homeassistant.components.school_holiday.config_flow import (
    CONF_CALENDAR_NAME,
    CONF_SENSOR_NAME,
)
from homeassistant.components.school_holiday.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION, TEST_SENSOR_NAME


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_SENSOR_NAME: TEST_SENSOR_NAME,
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "calendar"

    calendar_input = {CONF_CALENDAR_NAME: TEST_CALENDAR_NAME}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=calendar_input
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SENSOR_NAME] == TEST_SENSOR_NAME
    assert result["data"][CONF_COUNTRY] == TEST_COUNTRY
    assert result["data"][CONF_REGION] == TEST_REGION
    assert result["data"][CONF_CALENDAR_NAME] == TEST_CALENDAR_NAME
