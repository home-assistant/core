"""Define tests for the israel rail config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.israel_rail import CONF_DESTINATION, CONF_START, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import VALID_CONFIG


async def test_create_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_israelrail: AsyncMock
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "start destination"
    assert result2["data"] == {
        CONF_START: "start",
        CONF_DESTINATION: "destination",
    }


async def test_flow_fails(
    hass: HomeAssistant,
    mock_israelrail: AsyncMock,
) -> None:
    """Test that the user step fails."""
    mock_israelrail.return_value.query.side_effect = Exception("error")
    failed_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert failed_result["errors"] == {"base": "unknown"}

    mock_israelrail.return_value.query.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        failed_result["flow_id"],
        VALID_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "start destination"
    assert result["data"] == {
        CONF_START: "start",
        CONF_DESTINATION: "destination",
    }
