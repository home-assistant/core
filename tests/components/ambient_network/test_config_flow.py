"""Test the Ambient Weather Network config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aioambient import OpenAPI
import pytest

from homeassistant.components.ambient_network.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_happy_path(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    open_api: OpenAPI,
    devices_by_location: list[dict[str, Any]],
    config_entry: ConfigEntry,
) -> None:
    """Test the happy path."""

    setup_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert setup_result["type"] == FlowResultType.FORM
    assert setup_result["step_id"] == "user"
    assert setup_result["errors"] == {}

    with patch.object(
        open_api,
        "get_devices_by_location",
        AsyncMock(return_value=devices_by_location),
    ):
        user_result = await hass.config_entries.flow.async_configure(
            setup_result["flow_id"],
            {"location": {"latitude": 10.0, "longitude": 20.0, "radius": 1.0}},
        )

    assert user_result["type"] == FlowResultType.FORM
    assert user_result["step_id"] == "station"
    assert user_result["errors"] == {}

    stations_result = await hass.config_entries.flow.async_configure(
        user_result["flow_id"],
        {
            "station": "AA:AA:AA:AA:AA:AA,Station A1",
        },
    )

    assert stations_result["type"] == FlowResultType.FORM
    assert stations_result["step_id"] == "station_name"
    assert stations_result["errors"] == {}

    station_name_result = await hass.config_entries.flow.async_configure(
        stations_result["flow_id"], {"station_name": "virtual_station"}
    )

    assert station_name_result["type"] == FlowResultType.CREATE_ENTRY
    assert station_name_result["title"] == config_entry.title
    assert station_name_result["data"] == config_entry.data
    assert len(mock_setup_entry.mock_calls) == 1


async def test_no_station_found(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    open_api: OpenAPI,
    empty_devices_by_location: list[dict[str, Any]],
) -> None:
    """Test that we abort when we cannot find a station in the area."""

    setup_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert setup_result["type"] == FlowResultType.FORM
    assert setup_result["step_id"] == "user"
    assert setup_result["errors"] == {}

    with patch.object(
        open_api,
        "get_devices_by_location",
        AsyncMock(return_value=empty_devices_by_location),
    ):
        user_result = await hass.config_entries.flow.async_configure(
            setup_result["flow_id"],
            {"location": {"latitude": 10.0, "longitude": 20.0, "radius": 1.0}},
        )

    assert user_result["type"] == FlowResultType.ABORT
    assert user_result["reason"] == "no_stations_found"


async def test_empty_station_name(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    open_api: OpenAPI,
    devices_by_location: list[dict[str, Any]],
) -> None:
    """Test that we abort if the station name is empty."""

    setup_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert setup_result["type"] == FlowResultType.FORM
    assert setup_result["step_id"] == "user"
    assert setup_result["errors"] == {}

    with patch.object(
        open_api,
        "get_devices_by_location",
        AsyncMock(return_value=devices_by_location),
    ):
        user_result = await hass.config_entries.flow.async_configure(
            setup_result["flow_id"],
            {"location": {"latitude": 10.0, "longitude": 20.0, "radius": 1.0}},
        )

    assert user_result["type"] == FlowResultType.FORM
    assert user_result["step_id"] == "station"
    assert user_result["errors"] == {}

    stations_result = await hass.config_entries.flow.async_configure(
        user_result["flow_id"],
        {
            "station": "AA:AA:AA:AA:AA:AA,Station A1",
        },
    )

    station_name_result = await hass.config_entries.flow.async_configure(
        stations_result["flow_id"], {"station_name": ""}
    )

    assert station_name_result["type"] == FlowResultType.ABORT
    assert station_name_result["reason"] == "no_station_name_defined"
