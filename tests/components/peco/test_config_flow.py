"""Test the PECO Outage Counter config flow."""
from unittest.mock import patch

import pytest
from peco import HttpError, IncompatibleMeterError, UnresponsiveMeterError
from voluptuous.error import MultipleInvalid

from homeassistant import config_entries
from homeassistant.components.peco.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
    RESULT_TYPE_MENU,
    RESULT_TYPE_SHOW_PROGRESS,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_MENU

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "outage_counter"},
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "outage_counter"

    with patch(
        "homeassistant.components.peco.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "PHILADELPHIA",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Philadelphia Outage Count"
    assert result3["data"] == {
        "county": "PHILADELPHIA",
    }


async def test_invalid_county(hass: HomeAssistant) -> None:
    """Test if the InvalidCounty error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_MENU

    with pytest.raises(MultipleInvalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "INVALID_COUNTY_THAT_SHOULD_NOT_EXIST",
            },
        )
        await hass.async_block_till_done()

    second_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert second_result["type"] == RESULT_TYPE_MENU

    second_result2 = await hass.config_entries.flow.async_configure(
        second_result["flow_id"],
        {"next_step_id": "outage_counter"},
    )
    await hass.async_block_till_done()
    assert second_result2["type"] == RESULT_TYPE_FORM
    assert second_result2["step_id"] == "outage_counter"

    with patch(
        "homeassistant.components.peco.async_setup_entry",
        return_value=True,
    ):
        second_result3 = await hass.config_entries.flow.async_configure(
            second_result["flow_id"],
            {
                "county": "PHILADELPHIA",
            },
        )
        await hass.async_block_till_done()

    assert second_result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert second_result3["title"] == "Philadelphia Outage Count"
    assert second_result3["data"] == {
        "county": "PHILADELPHIA",
    }


async def test_meter_value_error(hass: HomeAssistant) -> None:
    """Test if the MeterValueError error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "smart_meter",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "smart_meter"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "phone_number": "INVALID_SMART_METER_THAT_SHOULD_NOT_EXIST",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_SHOW_PROGRESS
    assert result["step_id"] == "smart_meter"
    assert result["progress_action"] == "verifying_meter"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "smart_meter"
    assert result["errors"] == {"base": "invalid_phone_number"}


async def test_incompatible_meter_error(hass: HomeAssistant) -> None:
    """Test if the IncompatibleMeter error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "smart_meter",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "smart_meter"

    with patch("peco.PecoOutageApi.meter_check", side_effect=IncompatibleMeterError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "phone_number": "1234567890",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == RESULT_TYPE_SHOW_PROGRESS
        assert result["step_id"] == "smart_meter"
        assert result["progress_action"] == "verifying_meter"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "incompatible_meter"


async def test_unresponsive_meter_error(hass: HomeAssistant) -> None:
    """Test if the UnresponsiveMeter error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "smart_meter",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "smart_meter"

    with patch("peco.PecoOutageApi.meter_check", side_effect=UnresponsiveMeterError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "phone_number": "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_SHOW_PROGRESS
    assert result["step_id"] == "smart_meter"
    assert result["progress_action"] == "verifying_meter"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "smart_meter"
    assert result["errors"] == {"base": "unresponsive_meter"}


async def test_meter_http_error(hass: HomeAssistant) -> None:
    """Test if the InvalidMeter error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "smart_meter",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "smart_meter"

    with patch("peco.PecoOutageApi.meter_check", side_effect=HttpError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "phone_number": "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_SHOW_PROGRESS
    assert result["step_id"] == "smart_meter"
    assert result["progress_action"] == "verifying_meter"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "smart_meter"
    assert result["errors"] == {"base": "http_error"}


async def test_smart_meter(hass: HomeAssistant) -> None:
    """Test if the Smart Meter step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "smart_meter",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "smart_meter"

    with patch("peco.PecoOutageApi.meter_check", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "phone_number": "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_SHOW_PROGRESS
    assert result["step_id"] == "smart_meter"
    assert result["progress_action"] == "verifying_meter"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "1234567890 Smart Meter"
    assert result["data"]["phone_number"] == "1234567890"
