"""Define tests for the PurpleAir config flow."""
from unittest.mock import AsyncMock

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.purpleair import DOMAIN
from homeassistant.config_entries import SOURCE_USER


async def test_duplicate_error(hass, config_entry, setup_purpleair):
    """Test that the proper error is shown when adding a duplicate config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "check_api_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": "abcde12345"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "by_coordinates"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "latitude": 51.5285582,
            "longitude": -0.2416796,
            "distance": 5,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_entry_by_coordinates(hass, setup_purpleair):
    """Test creating an entry by entering a latitude/longitude."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "check_api_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": "abcde12345"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "by_coordinates"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "latitude": 51.5285582,
            "longitude": -0.2416796,
            "distance": 5,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Sensor"
    assert result["data"] == {
        "api_key": "abcde12345",
        "sensor_index": 123456,
    }


@pytest.mark.parametrize(
    "check_api_key,errors",
    [
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidApiKeyError), {"api_key": "invalid_api_key"}),
        (AsyncMock(side_effect=PurpleAirError), {"base": "unknown"}),
    ],
)
async def test_step_by_coordinates_api_errors(hass, errors, setup_purpleair):
    """Test API errors in the by_coordinates step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "check_api_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": "abcde12345"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == errors


@pytest.mark.parametrize(
    "get_nearby_sensors,errors",
    [
        (AsyncMock(return_value=[]), {"base": "no_sensors_near_coordinates"}),
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=PurpleAirError), {"base": "unknown"}),
    ],
)
async def test_step_by_coordinates_nearby_sensor_errors(
    hass, config_entry_data, errors, setup_purpleair
):
    """Test errors in the by_coordinates step during checking for nearby sensors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "check_api_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": "abcde12345"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "by_coordinates"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "latitude": 51.5285582,
            "longitude": -0.2416796,
            "distance": 5,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == errors
