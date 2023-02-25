"""Tests the Home Assistant workday config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.workday.const import (
    CONF_ADD_HOLIDAYS,
    CONF_REMOVE_HOLIDAYS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import init_integration
from .fixtures import (
    ASSUMED_DATE,
    SENSOR_DATA,
    USER_INPUT,
    USER_INPUT_ADD_BAD_HOLIDAY,
    USER_INPUT_ADD_HOLIDAY,
    USER_INPUT_REMOVE_HOLIDAYS,
    USER_INPUT_REMOVE_NONEXISTENT_HOLIDAYS,
)


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"


async def test_sensor_setup_success(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=SENSOR_DATA
    )

    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result.get("data", {}) == SENSOR_DATA


async def test_basic_setup_success(hass: HomeAssistant) -> None:
    """Test basic successful setup."""
    with patch(
        "homeassistant.components.workday.util.get_date",
        return_value=ASSUMED_DATE,
    ):
        entry = await init_integration(hass, SENSOR_DATA)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
        await hass.async_block_till_done()

        assert result2.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2.get("data", {}) == USER_INPUT


async def test_setup_adding_holidays(hass: HomeAssistant) -> None:
    """Test setup with adding holidays."""
    with patch(
        "homeassistant.components.workday.util.get_date",
        return_value=ASSUMED_DATE,
    ):
        entry = await init_integration(hass, SENSOR_DATA)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=USER_INPUT_ADD_HOLIDAY
        )
        await hass.async_block_till_done()

        assert result2.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2.get("data", {}) == USER_INPUT_ADD_HOLIDAY


async def test_setup_remove_holidays(hass: HomeAssistant) -> None:
    """Test setup with removing holidays."""
    with patch(
        "homeassistant.components.workday.util.get_date",
        return_value=ASSUMED_DATE,
    ):
        entry = await init_integration(hass, SENSOR_DATA)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=USER_INPUT_REMOVE_HOLIDAYS
        )
        await hass.async_block_till_done()

        assert result2.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2.get("data", {}) == USER_INPUT_REMOVE_HOLIDAYS


async def test_setup_add_invalid_holiday(hass: HomeAssistant) -> None:
    """Test setup with adding an invalid holiday."""
    with patch(
        "homeassistant.components.workday.util.get_date",
        return_value=ASSUMED_DATE,
    ):
        entry = await init_integration(hass, SENSOR_DATA)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=USER_INPUT_ADD_BAD_HOLIDAY
        )
        await hass.async_block_till_done()

        assert result2.get("type") == data_entry_flow.FlowResultType.FORM
        assert result2.get("step_id") == "init"
        assert result2.get("errors", {}) == {CONF_ADD_HOLIDAYS: "bad_holiday"}


async def test_setup_remove_nonexistent_holiday(hass: HomeAssistant) -> None:
    """Test setup with removing a holiday that doesn't exist."""
    with patch(
        "homeassistant.components.workday.util.get_date",
        return_value=ASSUMED_DATE,
    ):
        entry = await init_integration(hass, SENSOR_DATA)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=USER_INPUT_REMOVE_NONEXISTENT_HOLIDAYS
        )
        await hass.async_block_till_done()

        assert result2.get("type") == data_entry_flow.FlowResultType.FORM
        assert result2.get("step_id") == "init"
        assert result2.get("errors", {}) == {CONF_REMOVE_HOLIDAYS: "no_such_holiday"}
