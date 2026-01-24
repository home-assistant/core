"""Test the Green Planet Energy config flow."""

from unittest.mock import MagicMock

from greenplanet_energy_api import (
    GreenPlanetEnergyAPIError,
    GreenPlanetEnergyConnectionError,
)
import pytest

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


async def test_form_create_entry(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Green Planet Energy"
    assert result2["data"] == {}


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (GreenPlanetEnergyConnectionError("Connection failed"), "cannot_connect"),
        (GreenPlanetEnergyAPIError("API error"), "invalid_auth"),
        (Exception("Unknown error"), "unknown"),
    ],
)
async def test_form_errors_and_recovery(
    hass: HomeAssistant, mock_api: MagicMock, exception: Exception, error_base: str
) -> None:
    """Test handling errors and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Set the mock to raise an error
    mock_api.get_electricity_prices.side_effect = exception

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error_base}

    # Reset the mock to not raise an error and test recovery
    mock_api.get_electricity_prices.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Green Planet Energy"
    assert result3["data"] == {}


async def test_form_already_configured(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
