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
async def test_config_flow(hass: HomeAssistant) -> None:
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


@pytest.mark.asyncio
async def test_user_flow_empty_sensor_name(hass: HomeAssistant) -> None:
    """Test user flow with empty sensor name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    user_input = {
        CONF_SENSOR_NAME: "",
        CONF_COUNTRY: TEST_COUNTRY,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "required" in result["errors"].get(CONF_SENSOR_NAME, "")


@pytest.mark.asyncio
async def test_calendar_flow_empty_calendar_name(hass: HomeAssistant) -> None:
    """Test calendar flow with empty calendar name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    user_input = {
        CONF_SENSOR_NAME: TEST_SENSOR_NAME,
        CONF_COUNTRY: TEST_COUNTRY,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    region_input = {CONF_REGION: TEST_REGION}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=region_input
    )

    calendar_input = {CONF_CALENDAR_NAME: ""}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=calendar_input
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "calendar"
    assert "required" in result["errors"].get(CONF_CALENDAR_NAME, "")


@pytest.mark.asyncio
async def test_defaults_are_localized_for_locale_variant(
    hass: HomeAssistant,
) -> None:
    """Test defaults are localized for a language with region suffix."""
    hass.config.language = "nl-NL"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    sensor_name_key = next(
        schema_key
        for schema_key in result["data_schema"].schema
        if schema_key == CONF_SENSOR_NAME
    )

    assert sensor_name_key.default() == "Schoolvakantie Sensor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SENSOR_NAME: TEST_SENSOR_NAME,
            CONF_COUNTRY: TEST_COUNTRY,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REGION: TEST_REGION}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "calendar"

    calendar_name_key = next(
        schema_key
        for schema_key in result["data_schema"].schema
        if schema_key == CONF_CALENDAR_NAME
    )

    assert calendar_name_key.default() == "Schoolvakantie Kalender"


@pytest.mark.asyncio
async def test_defaults_are_localized_for_country_language_variant(
    hass: HomeAssistant,
) -> None:
    """Test defaults are localized when locale is formatted as country-language."""
    hass.config.language = "be-nl"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    sensor_name_key = next(
        schema_key
        for schema_key in result["data_schema"].schema
        if schema_key == CONF_SENSOR_NAME
    )

    assert sensor_name_key.default() == "Schoolvakantie Sensor"


@pytest.mark.asyncio
async def test_defaults_fallback_to_english_for_other_languages(
    hass: HomeAssistant,
) -> None:
    """Test defaults fall back to English when no translation exists."""
    hass.config.language = "fr"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    sensor_name_key = next(
        schema_key
        for schema_key in result["data_schema"].schema
        if schema_key == CONF_SENSOR_NAME
    )

    assert sensor_name_key.default() == "School Holiday Sensor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SENSOR_NAME: TEST_SENSOR_NAME,
            CONF_COUNTRY: TEST_COUNTRY,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REGION: TEST_REGION}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "calendar"

    calendar_name_key = next(
        schema_key
        for schema_key in result["data_schema"].schema
        if schema_key == CONF_CALENDAR_NAME
    )

    assert calendar_name_key.default() == "School Holiday Calendar"
