"""Test the Green Planet Energy config flow."""

from unittest.mock import AsyncMock, patch

from greenplanet_energy_api import (
    GreenPlanetEnergyAPIError,
    GreenPlanetEnergyConnectionError,
)

from homeassistant import config_entries
from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_user_init(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"


async def test_form_create_entry(hass: HomeAssistant) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.green_planet_energy.config_flow.GreenPlanetEnergyAPI"
    ) as mock_api_class:
        mock_api = AsyncMock()
        mock_api.get_electricity_prices.return_value = {"gpe_price_00": 0.25}
        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Green Planet Energy"
    assert result2["data"] == {}


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test handling connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.green_planet_energy.config_flow.GreenPlanetEnergyAPI"
    ) as mock_api_class:
        mock_api = AsyncMock()
        mock_api.get_electricity_prices.side_effect = GreenPlanetEnergyConnectionError(
            "Connection failed"
        )
        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_api_error(hass: HomeAssistant) -> None:
    """Test handling API error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.green_planet_energy.config_flow.GreenPlanetEnergyAPI"
    ) as mock_api_class:
        mock_api = AsyncMock()
        mock_api.get_electricity_prices.side_effect = GreenPlanetEnergyAPIError(
            "API error"
        )
        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test handling unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.green_planet_energy.config_flow.GreenPlanetEnergyAPI"
    ) as mock_api_class:
        mock_api = AsyncMock()
        mock_api.get_electricity_prices.side_effect = Exception("Unknown error")
        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
