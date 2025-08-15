"""Test the nsw_fuel_station config flow."""

from unittest.mock import MagicMock

from nsw_fuel import FuelCheckError

from homeassistant import config_entries
from homeassistant.components.nsw_fuel_station.const import (
    CONF_FUEL_TYPES,
    CONF_STATION_ID,
    DOMAIN,
    INPUT_SEARCH_TERM,
    INPUT_STATION_ID,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_fuelcheckclient: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_SEARCH_TERM: "Unmatched",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"].get("base") == "no_matching_stations"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_SEARCH_TERM: "Anytown",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_STATION_ID: "222",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["result"].data == {
        CONF_STATION_ID: 222,
    }


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_fuelcheckclient: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test attempt to add duplicate entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_SEARCH_TERM: "AnyTown",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            INPUT_STATION_ID: "222",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_client_error(
    hass: HomeAssistant, mock_fuelcheckclient: MagicMock
) -> None:
    """Test flow is aborted on client error."""
    mock_fuelcheckclient.get_fuel_prices.side_effect = FuelCheckError
    mock_fuelcheckclient.get_reference_data.side_effect = FuelCheckError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "fetch_failed"


async def test_import_flow_ok(hass: HomeAssistant) -> None:
    """Test the import configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_STATION_ID: 222,
            CONF_FUEL_TYPES: ["E10", "DL"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Station 222"
    assert result["data"] == {
        CONF_STATION_ID: 222,
    }
    assert result["options"] == {}


async def test_import_flow_empty_config(
    hass: HomeAssistant,
) -> None:
    """Test the import configuration flow, station not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_config"
