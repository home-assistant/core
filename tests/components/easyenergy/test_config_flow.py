"""Test the easyEnergy config flow."""

from unittest.mock import MagicMock, patch

from easyenergy import EasyEnergyConnectionError

from homeassistant.components.easyenergy.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_easyenergy: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    with patch(
        "homeassistant.components.easyenergy.config_flow.EasyEnergy",
        return_value=mock_easyenergy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "user"
        assert "flow_id" in result

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "easyEnergy"
    assert result2.get("data") == {}

    assert mock_easyenergy.energy_prices.call_count == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_easyenergy: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test we handle connection errors and recover."""
    mock_easyenergy.energy_prices.side_effect = [
        EasyEnergyConnectionError,
        mock_easyenergy.energy_prices.return_value,
    ]

    with patch(
        "homeassistant.components.easyenergy.config_flow.EasyEnergy",
        return_value=mock_easyenergy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "easyEnergy"
    assert result["data"] == {}

    assert mock_easyenergy.energy_prices.call_count == 2
    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_instance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test abort when setting up a duplicate entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"
