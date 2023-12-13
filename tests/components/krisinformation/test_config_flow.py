"""Test the krisinformation config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from voluptuous import MultipleInvalid

from homeassistant import config_entries
from homeassistant.components.krisinformation.const import COUNTY_CODES, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "county": COUNTY_CODES["17"],
            "name": "Krisinformation - Test",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Krisinformation - Test"
    assert result2["data"] == {
        "county": COUNTY_CODES["17"],
        "name": "Krisinformation - Test",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_invalid_county(hass: HomeAssistant) -> None:
    """Test we handle invalid county error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    try:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"county": "invalid_county"},
        )
    except MultipleInvalid as err:
        assert (
            str(err)
            == "value must be one of ['Blekinge län', 'Dalarnas län', 'Gotlands län', 'Gävleborgs län', 'Hallands län', 'Jämtlands län', 'Jönköpings län', 'Kalmar län', 'Kronobergs län', 'Norrbottens län', 'Skåne län', 'Stockholms län', 'Södermanlands län', 'Uppsala län', 'Värmlands län', 'Västerbottens län', 'Västernorrlands län', 'Västmanlands län', 'Västra Götalands län', 'Örebro län', 'Östergötlands län'] for dictionary value @ data['county']"
        )

    assert result["errors"] == {}
