"""Tests for the Daily Schedule config flow."""
from homeassistant.components.daily_schedule.config_flow import (
    ADD_PERIOD,
    PERIOD_DELIMITER,
)
from homeassistant.components.daily_schedule.const import (
    ATTR_END,
    ATTR_SCHEDULE,
    ATTR_START,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_config_flow_no_schedule(hass: HomeAssistant) -> None:
    """Test the user flow without a schedule."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "test", ADD_PERIOD: False},
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "test"
    assert result2.get("options") == {ATTR_SCHEDULE: []}


async def test_config_flow_with_schedule(hass: HomeAssistant) -> None:
    """Test the user flow with a schedule."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "test"},  # Default is to add a time period
    )
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "period"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={ATTR_START: "15:00:00", ATTR_END: "20:00:00", ADD_PERIOD: True},
    )
    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("step_id") == "period"

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={ATTR_START: "05:00:00", ATTR_END: "10:00:00"},
    )
    assert result4.get("type") == FlowResultType.CREATE_ENTRY
    assert result4.get("title") == "test"
    assert result4.get("options") == {
        ATTR_SCHEDULE: [
            {ATTR_START: "05:00:00", ATTR_END: "10:00:00"},
            {ATTR_START: "15:00:00", ATTR_END: "20:00:00"},
        ]
    }


async def test_config_flow_invalid_schedule(hass: HomeAssistant) -> None:
    """Test the user flow with an invalid schedule."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "test"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={ATTR_START: "05:00:00", ATTR_END: "10:00:00", ADD_PERIOD: True},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={ATTR_START: "03:00:00", ATTR_END: "06:00:00"},
    )
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "period"
    assert result2.get("errors")["base"] == "invalid_schedule"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Test",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_START: "01:00:00",
            ATTR_END: "04:00:00",
        },
    )
    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("data") == {
        ATTR_SCHEDULE: [
            {ATTR_START: "01:00:00", ATTR_END: "04:00:00"},
        ]
    }


async def test_invalid_options_flow(hass: HomeAssistant) -> None:
    """Test invalid options flow."""
    config_entry = MockConfigEntry(
        options={ATTR_SCHEDULE: [{ATTR_START: "05:00:00", ATTR_END: "10:00:00"}]},
        domain=DOMAIN,
        title="My Test",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_SCHEDULE: [f"05:00:00{PERIOD_DELIMITER}10:00:00"],
            ADD_PERIOD: True,
            ATTR_START: "01:00:00",
            ATTR_END: "06:00:00",
        },
    )
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors")["base"] == "invalid_schedule"
