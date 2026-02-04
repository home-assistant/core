"""Test the Green Planet Energy config flow."""

from unittest.mock import AsyncMock, MagicMock

from greenplanet_energy_api import (
    GreenPlanetEnergyAPIError,
    GreenPlanetEnergyConnectionError,
)
import pytest

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_create_entry(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Green Planet Energy"
    assert result["data"] == {}


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (GreenPlanetEnergyConnectionError("Connection failed"), "cannot_connect"),
        (GreenPlanetEnergyAPIError("API error"), "invalid_auth"),
        (Exception("Unknown error"), "unknown"),
    ],
)
async def test_form_errors_and_recovery(
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test handling errors and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Set the mock to raise an error
    mock_api.get_electricity_prices.side_effect = exception

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Reset the mock to not raise an error and test recovery
    mock_api.get_electricity_prices.side_effect = None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
