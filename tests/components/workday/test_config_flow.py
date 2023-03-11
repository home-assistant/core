"""Test the Workday config flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.workday.const import (
    CONF_ADD_HOLIDAYS,
    CONF_COUNTRY,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_NAME,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import init_integration

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the forms."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.workday.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Workday Sensor",
                CONF_COUNTRY: "DE",
            },
        )
        await hass.async_block_till_done()
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_EXCLUDES: DEFAULT_EXCLUDES,
                CONF_OFFSET: DEFAULT_OFFSET,
                CONF_WORKDAYS: DEFAULT_WORKDAYS,
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: [],
                CONF_PROVINCE: "None",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor"
    assert result3["options"] == {
        "name": "Workday Sensor",
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "add_holidays": [],
        "remove_holidays": [],
        "province": "None",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.workday.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_NAME: DEFAULT_NAME,
                CONF_COUNTRY: "DE",
                CONF_EXCLUDES: DEFAULT_EXCLUDES,
                CONF_OFFSET: DEFAULT_OFFSET,
                CONF_WORKDAYS: DEFAULT_WORKDAYS,
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: [],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Workday Sensor"
    assert result["options"] == {
        "name": "Workday Sensor",
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "add_holidays": [],
        "remove_holidays": [],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "name": "Workday Sensor",
            "country": "DE",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "add_holidays": [],
            "remove_holidays": [],
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.workday.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_COUNTRY: "DE",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_form(hass: HomeAssistant) -> None:
    """Test we get the form in options."""

    entry = await init_integration(
        hass,
        {
            "name": "Workday Sensor",
            "country": "DE",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "add_holidays": [],
            "remove_holidays": [],
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "add_holidays": [],
            "remove_holidays": [],
            "province": "BW",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "name": "Workday Sensor",
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "add_holidays": [],
        "remove_holidays": [],
        "province": "BW",
    }
    entry_check = hass.config_entries.async_get_entry("1")
    assert entry_check.state == config_entries.ConfigEntryState.LOADED
    assert entry_check.update_listeners is not None


async def test_form_incorrect_dates(hass: HomeAssistant) -> None:
    """Test errors in setup entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.workday.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Workday Sensor",
                CONF_COUNTRY: "DE",
            },
        )
        await hass.async_block_till_done()
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_EXCLUDES: DEFAULT_EXCLUDES,
                CONF_OFFSET: DEFAULT_OFFSET,
                CONF_WORKDAYS: DEFAULT_WORKDAYS,
                CONF_ADD_HOLIDAYS: ["2022-xx-12"],
                CONF_REMOVE_HOLIDAYS: [],
                CONF_PROVINCE: "None",
            },
        )
        await hass.async_block_till_done()
        assert result3["errors"] == {"add_holidays": "add_holiday_error"}

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_EXCLUDES: DEFAULT_EXCLUDES,
                CONF_OFFSET: DEFAULT_OFFSET,
                CONF_WORKDAYS: DEFAULT_WORKDAYS,
                CONF_ADD_HOLIDAYS: ["2022-12-12"],
                CONF_REMOVE_HOLIDAYS: ["Does not exist"],
                CONF_PROVINCE: "None",
            },
        )
        await hass.async_block_till_done()

        assert result3["errors"] == {"remove_holidays": "remove_holiday_error"}

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_EXCLUDES: DEFAULT_EXCLUDES,
                CONF_OFFSET: DEFAULT_OFFSET,
                CONF_WORKDAYS: DEFAULT_WORKDAYS,
                CONF_ADD_HOLIDAYS: ["2022-12-12"],
                CONF_REMOVE_HOLIDAYS: ["Weihnachtstag"],
                CONF_PROVINCE: "None",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor"
    assert result3["options"] == {
        "name": "Workday Sensor",
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "add_holidays": ["2022-12-12"],
        "remove_holidays": ["Weihnachtstag"],
        "province": "None",
    }


async def test_options_form_incorrect_dates(hass: HomeAssistant) -> None:
    """Test errors in options."""

    entry = await init_integration(
        hass,
        {
            "name": "Workday Sensor",
            "country": "DE",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "add_holidays": [],
            "remove_holidays": [],
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "add_holidays": ["2022-xx-12"],
            "remove_holidays": [],
            "province": "BW",
        },
    )

    assert result2["errors"] == {"add_holidays": "add_holiday_error"}

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "add_holidays": ["2022-12-12"],
            "remove_holidays": ["Does not exist"],
            "province": "BW",
        },
    )

    assert result2["errors"] == {"remove_holidays": "remove_holiday_error"}

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "add_holidays": ["2022-12-12"],
            "remove_holidays": ["Weihnachtstag"],
            "province": "BW",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "name": "Workday Sensor",
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "add_holidays": ["2022-12-12"],
        "remove_holidays": ["Weihnachtstag"],
        "province": "BW",
    }
