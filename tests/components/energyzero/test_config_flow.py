"""Test the EnergyZero config flow."""
from unittest.mock import patch

from energyzero import EnergyZeroError

from homeassistant.components.energyzero.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    with patch(
        "homeassistant.components.energyzero.config_flow.EnergyZero.energy_prices"
    ) as mock_energyzero, patch(
        "homeassistant.components.energyzero.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "EnergyZero"
    assert result2.get("data") == {}

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_energyzero.mock_calls) == 1


async def test_api_error(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.energyzero.coordinator.EnergyZero.energy_prices",
        side_effect=EnergyZeroError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={},
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}
