"""Test the Holiday config flow."""
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.holiday.const import CONF_PROVINCE, DOMAIN
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "DE",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_PROVINCE: "BW",
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Germany, BW"
    assert result3["data"] == {
        "country": "DE",
        "province": "BW",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_subdivision(hass: HomeAssistant) -> None:
    """Test we get the forms correctly without subdivision."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "SE",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sweden"
    assert result2["data"] == {
        "country": "SE",
    }


async def test_form_translated_title(hass: HomeAssistant) -> None:
    """Test the title gets translated."""
    hass.config.language = "de"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "SE",
        },
    )
    await hass.async_block_till_done()

    assert result2["title"] == "Schweden"


async def test_single_combination_country_province(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    data_de = {
        CONF_COUNTRY: "DE",
        CONF_PROVINCE: "BW",
    }
    data_se = {
        CONF_COUNTRY: "SE",
    }
    MockConfigEntry(domain=DOMAIN, data=data_de).add_to_hass(hass)
    MockConfigEntry(domain=DOMAIN, data=data_se).add_to_hass(hass)

    # Test for country without subdivisions
    result_se = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=data_se,
    )
    assert result_se["type"] == FlowResultType.ABORT
    assert result_se["reason"] == "already_configured"

    # Test for country with subdivisions
    result_de_step1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=data_de,
    )
    assert result_de_step1["type"] == FlowResultType.FORM

    result_de_step2 = await hass.config_entries.flow.async_configure(
        result_de_step1["flow_id"],
        {
            CONF_PROVINCE: data_de[CONF_PROVINCE],
        },
    )
    assert result_de_step2["type"] == FlowResultType.ABORT
    assert result_de_step2["reason"] == "already_configured"


async def test_form_babel_unresolved_language(hass: HomeAssistant) -> None:
    """Test the config flow if using not babel supported language."""
    hass.config.language = "en-XX"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "SE",
        },
    )
    await hass.async_block_till_done()

    assert result["title"] == "Sweden"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "DE",
        },
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PROVINCE: "BW",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Germany, BW"
    assert result["data"] == {
        "country": "DE",
        "province": "BW",
    }


async def test_form_babel_replace_dash_with_underscore(hass: HomeAssistant) -> None:
    """Test the config flow if using language with dash."""
    hass.config.language = "en-GB"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "SE",
        },
    )
    await hass.async_block_till_done()

    assert result["title"] == "Sweden"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "DE",
        },
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PROVINCE: "BW",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Germany, BW"
    assert result["data"] == {
        "country": "DE",
        "province": "BW",
    }
