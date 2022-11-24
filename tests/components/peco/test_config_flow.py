"""Test the PECO Outage Counter config flow."""
from unittest.mock import patch

from pytest import raises
from voluptuous.error import MultipleInvalid

from spencerassistant import config_entries
from spencerassistant.components.peco.const import DOMAIN
from spencerassistant.core import spencerAssistant
from spencerassistant.data_entry_flow import FlowResultType


async def test_form(hass: spencerAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "spencerassistant.components.peco.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "county": "PHILADELPHIA",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Philadelphia Outage Count"
    assert result2["data"] == {
        "county": "PHILADELPHIA",
    }


async def test_invalid_county(hass: spencerAssistant) -> None:
    """Test if the InvalidCounty error works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with raises(MultipleInvalid):
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
    assert second_result["type"] == FlowResultType.FORM
    assert second_result["errors"] is None

    with patch(
        "spencerassistant.components.peco.async_setup_entry",
        return_value=True,
    ):
        second_result2 = await hass.config_entries.flow.async_configure(
            second_result["flow_id"],
            {
                "county": "PHILADELPHIA",
            },
        )
        await hass.async_block_till_done()

    assert second_result2["type"] == FlowResultType.CREATE_ENTRY
    assert second_result2["title"] == "Philadelphia Outage Count"
    assert second_result2["data"] == {
        "county": "PHILADELPHIA",
    }
