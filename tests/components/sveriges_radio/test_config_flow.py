"""Test the Sveriges Radio config flow."""
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sveriges_radio.const import (
    AREAS,
    CONF_AREA,
    DOMAIN,
    TITLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")
area = AREAS[0]


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
            CONF_AREA: area,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == TITLE
    assert result2["data"] == {
        CONF_AREA: area,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_traffic_area(hass: HomeAssistant) -> None:
    """Test that an invalid area raises an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with pytest.raises(vol.error.MultipleInvalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_AREA: "",
            },
        )
        await hass.async_block_till_done()


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_AREA: area})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_onboarding_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the onboarding configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "onboarding"}
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Sveriges Radio"
    assert result.get("data") == {}

    assert len(mock_setup_entry.mock_calls) == 1
