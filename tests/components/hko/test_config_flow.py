"""Test the Hong Kong Observatory config flow."""

from unittest.mock import patch

from hko import HKOError

from homeassistant.components.hko.const import DEFAULT_LOCATION, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_flow_default(hass: HomeAssistant) -> None:
    """Test user config flow with default fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: DEFAULT_LOCATION},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEFAULT_LOCATION
    assert result2["result"].unique_id == DEFAULT_LOCATION
    assert result2["data"][CONF_LOCATION] == DEFAULT_LOCATION


async def test_config_flow_invalid_location(hass: HomeAssistant) -> None:
    """Test user config flow with an invalid location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_LOCATION: ""},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_location"


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user config flow without connection to the API."""
    with patch(
        "homeassistant.components.hko.config_flow.HKO.weather",
        side_effect=HKOError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_LOCATION: DEFAULT_LOCATION},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_unknown_exception(hass: HomeAssistant) -> None:
    """Test user config flow when an unknown exception occurs."""
    with patch(
        "homeassistant.components.hko.config_flow.HKO.weather",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_LOCATION: DEFAULT_LOCATION},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"
