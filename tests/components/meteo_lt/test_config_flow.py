"""Test the Meteo.lt config flow."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant.components.meteo_lt.const import CONF_PLACE_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow shows form and completes successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PLACE_CODE: "vilnius"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vilnius"
    assert result["data"] == {CONF_PLACE_CODE: "vilnius"}
    assert result["result"].unique_id == "vilnius"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate entry prevention."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PLACE_CODE: "vilnius"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(mock_setup_entry.mock_calls) == 0


async def test_api_connection_error(
    hass: HomeAssistant, mock_meteo_lt_api: AsyncMock
) -> None:
    """Test API connection error during place fetching."""
    mock_meteo_lt_api.places = []
    mock_meteo_lt_api.fetch_places.side_effect = aiohttp.ClientError(
        "Connection failed"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_api_timeout_error(
    hass: HomeAssistant, mock_meteo_lt_api: AsyncMock
) -> None:
    """Test API timeout error during place fetching."""
    mock_meteo_lt_api.places = []
    mock_meteo_lt_api.fetch_places.side_effect = TimeoutError("Request timed out")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_no_places_found(
    hass: HomeAssistant, mock_meteo_lt_api: AsyncMock
) -> None:
    """Test when API returns no places."""
    mock_meteo_lt_api.places = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_places_found"
