"""Test the Workday config flow."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
from holidays import HALF_DAY, OPTIONAL
import pytest

from homeassistant import config_entries
from homeassistant.components.workday.const import (
    CONF_ADD_HOLIDAYS,
    CONF_CATEGORY,
    CONF_EXCLUDES,
    CONF_INCLUDE_SUNDAYS,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
    SECTION_COUNTRY_SETTINGS,
    SECTION_CUSTOM_HOLIDAYS,
)
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util.dt import UTC

from . import init_integration


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(hass: HomeAssistant) -> None:
    """Test we get the forms."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
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
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: [],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "en_US",
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor DE"
    assert result3["options"] == {
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
        "country_settings": {
            "language": "en_US",
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_province_no_alias(hass: HomeAssistant) -> None:
    """Test we get the forms."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "US",
        },
    )
    await hass.async_block_till_done()
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: [],
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor US"
    assert result3["options"] == {
        "country": "US",
        "excludes": ["sat", "sun", "holiday"],
        "country_settings": {
            "language": "en_US",
        },
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_no_country(hass: HomeAssistant) -> None:
    """Test we get the forms correctly without a country."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: [],
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor"
    assert result3["options"] == {
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_country_without_settings(hass: HomeAssistant) -> None:
    """Test the country settings section is not shown when a country has none."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY: "AG"},
    )
    assert result["type"] is FlowResultType.FORM
    assert SECTION_CUSTOM_HOLIDAYS in result["data_schema"].schema
    assert SECTION_COUNTRY_SETTINGS not in result["data_schema"].schema

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        "country": "AG",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_no_subdivision(hass: HomeAssistant) -> None:
    """Test we get the forms correctly without subdivision."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "SE",
        },
    )
    await hass.async_block_till_done()
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: [],
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor SE"
    assert result3["options"] == {
        "country": "SE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
        "country_settings": {
            "language": "sv",
            "include_sundays": False,
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_form(hass: HomeAssistant) -> None:
    """Test we get the form in options."""

    entry = await init_integration(
        hass,
        {
            "country": "DE",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "language": "de",
            },
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "province": "BW",
                "language": "de",
            },
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
        "country_settings": {
            "province": "BW",
            "language": "de",
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_incorrect_dates(hass: HomeAssistant) -> None:
    """Test errors in setup entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
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
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: ["2022-xx-12"],
                CONF_REMOVE_HOLIDAYS: [],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "de",
            },
        },
    )
    await hass.async_block_till_done()
    assert result3["errors"] == {"custom_holidays": "add_holiday_error"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: ["2022-12-12"],
                CONF_REMOVE_HOLIDAYS: ["Does not exist"],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "de",
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["errors"] == {"custom_holidays": "remove_holiday_error"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: ["2022-12-12"],
                CONF_REMOVE_HOLIDAYS: ["Weihnachtstag"],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "de",
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor DE"
    assert result3["options"] == {
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": ["2022-12-12"],
            "remove_holidays": ["Weihnachtstag"],
        },
        "country_settings": {
            "language": "de",
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_form_incorrect_dates(hass: HomeAssistant) -> None:
    """Test errors in options."""

    entry = await init_integration(
        hass,
        {
            "country": "DE",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "language": "de",
            },
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": ["2022-xx-12"],
                "remove_holidays": [],
            },
            "country_settings": {
                "province": "BW",
                "language": "de",
            },
        },
    )

    assert result2["errors"] == {"custom_holidays": "add_holiday_error"}

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": ["2022-12-12"],
                "remove_holidays": ["Does not exist"],
            },
            "country_settings": {
                "province": "BW",
                "language": "de",
            },
        },
    )

    assert result2["errors"] == {"custom_holidays": "remove_holiday_error"}

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": ["2022-12-12"],
                "remove_holidays": ["Weihnachtstag"],
            },
            "country_settings": {
                "province": "BW",
                "language": "de",
            },
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": ["2022-12-12"],
            "remove_holidays": ["Weihnachtstag"],
        },
        "country_settings": {
            "province": "BW",
            "language": "de",
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_form_abort_duplicate(hass: HomeAssistant) -> None:
    """Test errors in options for duplicates."""

    await init_integration(
        hass,
        {
            "country": "CH",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "province": "FR",
                "language": "de",
                "category": [OPTIONAL],
            },
        },
        entry_id="1",
    )
    entry2 = await init_integration(
        hass,
        {
            "country": "CH",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": ["2023-03-28"],
                "remove_holidays": [],
            },
            "country_settings": {
                "province": "FR",
                "language": "de",
                "category": [OPTIONAL],
            },
        },
        entry_id="2",
    )

    result = await hass.config_entries.options.async_init(entry2.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0.0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "province": "FR",
                "category": [OPTIONAL],
            },
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "already_configured"}

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0.0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": ["2023-03-29"],
                "remove_holidays": [],
            },
            "country_settings": {
                "province": "FR",
                "category": [OPTIONAL],
            },
        },
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_incorrect_date_range(hass: HomeAssistant) -> None:
    """Test errors in setup entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
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
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: ["2022-12-12", "2022-12-30,2022-12-32"],
                CONF_REMOVE_HOLIDAYS: [],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "de",
            },
        },
    )
    await hass.async_block_till_done()
    assert result3["errors"] == {"custom_holidays": "add_holiday_range_error"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: ["2022-12-12"],
                CONF_REMOVE_HOLIDAYS: ["2022-12-25", "2022-12-30,2022-12-32"],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "de",
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["errors"] == {"custom_holidays": "remove_holiday_range_error"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: ["2022-12-12", "2022-12-01,2022-12-10"],
                CONF_REMOVE_HOLIDAYS: ["2022-12-25", "2022-12-30,2022-12-31"],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "de",
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor DE"
    assert result3["options"] == {
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": ["2022-12-12", "2022-12-01,2022-12-10"],
            "remove_holidays": ["2022-12-25", "2022-12-30,2022-12-31"],
        },
        "country_settings": {
            "language": "de",
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_form_incorrect_date_ranges(hass: HomeAssistant) -> None:
    """Test errors in options."""

    entry = await init_integration(
        hass,
        {
            "country": "DE",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "language": "de",
            },
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": ["2022-12-30,2022-12-32"],
                "remove_holidays": [],
            },
            "country_settings": {
                "province": "BW",
                "language": "de",
            },
        },
    )

    assert result2["errors"] == {"custom_holidays": "add_holiday_range_error"}

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": ["2022-12-30,2022-12-31"],
                "remove_holidays": ["2022-13-25,2022-12-26"],
            },
            "country_settings": {
                "province": "BW",
                "language": "de",
            },
        },
    )

    assert result2["errors"] == {"custom_holidays": "remove_holiday_range_error"}

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": ["2022-12-30,2022-12-31"],
                "remove_holidays": ["2022-12-25,2022-12-26"],
            },
            "country_settings": {
                "province": "BW",
                "language": "de",
            },
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": ["2022-12-30,2022-12-31"],
            "remove_holidays": ["2022-12-25,2022-12-26"],
        },
        "country_settings": {
            "province": "BW",
            "language": "de",
        },
    }


@pytest.mark.parametrize(
    ("language", "holiday"),
    [
        ("de", "Weihnachtstag"),
        ("en_US", "Christmas"),
    ],
)
async def test_language(
    hass: HomeAssistant, language: str, holiday: str, freezer: FrozenDateTimeFactory
) -> None:
    """Test we get the forms."""
    freezer.move_to(datetime(2023, 12, 25, 12, tzinfo=UTC))  # Monday

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
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
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: [holiday],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: language,
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor DE"
    assert result3["options"] == {
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [holiday],
        },
        "country_settings": {
            "language": language,
        },
    }

    state = hass.states.get("binary_sensor.workday_sensor_de")
    assert state is not None
    assert state.state == "on"


async def test_form_with_categories(hass: HomeAssistant) -> None:
    """Test optional categories."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "CH",
        },
    )
    await hass.async_block_till_done()
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: [],
            },
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "de",
                CONF_CATEGORY: [HALF_DAY],
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor CH"
    assert result3["options"] == {
        "country": "CH",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
        "country_settings": {
            "language": "de",
            "category": ["half_day"],
        },
    }


async def test_form_with_categories_can_remove_day(hass: HomeAssistant) -> None:
    """Test optional categories, days can be removed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "CH",
        },
    )
    await hass.async_block_till_done()
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            SECTION_COUNTRY_SETTINGS: {
                CONF_PROVINCE: "FR",
                CONF_LANGUAGE: "de",
                CONF_CATEGORY: [OPTIONAL],
            },
            CONF_EXCLUDES: DEFAULT_EXCLUDES,
            CONF_OFFSET: DEFAULT_OFFSET,
            CONF_WORKDAYS: DEFAULT_WORKDAYS,
            SECTION_CUSTOM_HOLIDAYS: {
                CONF_ADD_HOLIDAYS: [],
                CONF_REMOVE_HOLIDAYS: ["Berchtoldstag"],
            },
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Workday Sensor CH FR"
    assert result3["options"] == {
        "country": "CH",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": ["Berchtoldstag"],
        },
        "country_settings": {
            "province": "FR",
            "language": "de",
            "category": ["optional"],
        },
    }


async def test_options_form_removes_subdiv(hass: HomeAssistant) -> None:
    """Test we get the form in options when removing a configured subdivision."""

    entry = await init_integration(
        hass,
        {
            "country": "DE",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "language": "de",
                "province": "BW",
            },
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "language": "de",
            },
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "country": "DE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
        "country_settings": {
            "language": "de",
        },
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_country_options(hass: HomeAssistant) -> None:
    """Test the country specific options are used to validate removed holidays."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY: "SE"},
    )
    user_input = {
        CONF_EXCLUDES: DEFAULT_EXCLUDES,
        CONF_OFFSET: DEFAULT_OFFSET,
        CONF_WORKDAYS: DEFAULT_WORKDAYS,
        SECTION_CUSTOM_HOLIDAYS: {
            CONF_ADD_HOLIDAYS: [],
            CONF_REMOVE_HOLIDAYS: ["Söndag"],
        },
    }

    # Sundays are only named holidays when the option is enabled
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **user_input,
            SECTION_COUNTRY_SETTINGS: {
                CONF_LANGUAGE: "sv",
                CONF_INCLUDE_SUNDAYS: False,
            },
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"custom_holidays": "remove_holiday_error"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **user_input,
            SECTION_COUNTRY_SETTINGS: {CONF_LANGUAGE: "sv", CONF_INCLUDE_SUNDAYS: True},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        "country": "SE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": ["Söndag"],
        },
        "country_settings": {
            "language": "sv",
            "include_sundays": True,
        },
    }


async def test_options_form_country_options(hass: HomeAssistant) -> None:
    """Test changing a country specific option in the options flow."""

    entry = await init_integration(
        hass,
        {
            "country": "SE",
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "language": "sv",
                "include_sundays": False,
            },
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "excludes": ["sat", "sun", "holiday"],
            "days_offset": 0,
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "custom_holidays": {
                "add_holidays": [],
                "remove_holidays": [],
            },
            "country_settings": {
                "language": "sv",
                "include_sundays": True,
            },
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "country": "SE",
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "custom_holidays": {
            "add_holidays": [],
            "remove_holidays": [],
        },
        "country_settings": {
            "language": "sv",
            "include_sundays": True,
        },
    }
