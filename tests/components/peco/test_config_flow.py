"""Test the PECO Outage Counter config flow."""

from unittest.mock import patch

from peco import HttpError, IncompatibleMeterError, UnresponsiveMeterError
import pytest
from voluptuous.error import Invalid

from homeassistant import config_entries
from homeassistant.components.peco.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.peco.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "PHILADELPHIA",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Philadelphia Outage Count"
    assert result2["data"] == {
        "county": "PHILADELPHIA",
    }
    assert result2["context"]["unique_id"] == "PHILADELPHIA"


async def test_invalid_county(hass: HomeAssistant) -> None:
    """Test if the InvalidCounty error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.peco.async_setup_entry",
            return_value=True,
        ),
        pytest.raises(Invalid),
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "INVALID_COUNTY_THAT_SHOULDNT_EXIST",
            },
        )
        await hass.async_block_till_done()


async def test_meter_value_error(hass: HomeAssistant) -> None:
    """Test if the MeterValueError error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "county": "PHILADELPHIA",
            "phone_number": "INVALID_SMART_METER_THAT_SHOULD_NOT_EXIST",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"phone_number": "invalid_phone_number"}


async def test_incompatible_meter_error(hass: HomeAssistant) -> None:
    """Test if the IncompatibleMeter error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("peco.PecoOutageApi.meter_check", side_effect=IncompatibleMeterError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "PHILADELPHIA",
                "phone_number": "1234567890",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "incompatible_meter"


async def test_unresponsive_meter_error(hass: HomeAssistant) -> None:
    """Test if the UnresponsiveMeter error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("peco.PecoOutageApi.meter_check", side_effect=UnresponsiveMeterError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "PHILADELPHIA",
                "phone_number": "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"phone_number": "unresponsive_meter"}


async def test_meter_http_error(hass: HomeAssistant) -> None:
    """Test if the InvalidMeter error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("peco.PecoOutageApi.meter_check", side_effect=HttpError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "PHILADELPHIA",
                "phone_number": "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"phone_number": "http_error"}


async def test_smart_meter(hass: HomeAssistant) -> None:
    """Test if the Smart Meter step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("peco.PecoOutageApi.meter_check", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "PHILADELPHIA",
                "phone_number": "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Philadelphia - 1234567890"
    assert result["data"]["phone_number"] == "1234567890"
    assert result["context"]["unique_id"] == "PHILADELPHIA-1234567890"
