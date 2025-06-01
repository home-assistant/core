"""Test the nsw_fuel_station config flow."""

from unittest.mock import MagicMock

from nsw_fuel import FuelCheckError
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.nsw_fuel_station.const import (
    CONF_FUEL_TYPES,
    CONF_STATION_ID,
    DOMAIN,
    INPUT_FUEL_TYPES,
    INPUT_SEARCH_TERM,
    INPUT_STATION_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_fuelcheckclient")
async def test_form(hass: HomeAssistant, mock_fuelcheckclient: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_SEARCH_TERM: "Anytown",
        },
    )

    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_STATION_ID: "222",
        },
    )

    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_FUEL_TYPES: ["E10", "DL"],
        },
    )

    await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result4["result"]
    assert config_entry.data == {
        CONF_STATION_ID: 222,
        CONF_FUEL_TYPES: ["E10", "DL"],
    }


@pytest.mark.usefixtures("mock_fuelcheckclient")
async def test_invalid_fueltype(
    hass: HomeAssistant, mock_fuelcheckclient: MagicMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_SEARCH_TERM: "Anytown",
        },
    )

    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_STATION_ID: "222",
        },
    )

    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM

    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                INPUT_FUEL_TYPES: ["P95", "DL"],
            },
        )


@pytest.mark.usefixtures("mock_fuelcheckclient")
async def test_client_error(
    hass: HomeAssistant, mock_fuelcheckclient: MagicMock
) -> None:
    """Test we get the form."""
    mock_fuelcheckclient.get_reference_data.side_effect = FuelCheckError

    with pytest.raises(ConfigEntryNotReady):
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
