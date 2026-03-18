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


@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_happy_path(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    open_api: OpenAPI,
    aioambient: AsyncMock,
    devices_by_location: list[dict[str, Any]],
    config_entry: ConfigEntry,
) -> None:
    """Test the happy path."""

    setup_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert setup_result["type"] == FlowResultType.FORM
    assert setup_result["step_id"] == "user"

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

    stations_result = await hass.config_entries.flow.async_configure(
        user_result["flow_id"],
        {
            "station": "AA:AA:AA:AA:AA:AA",
        },
    )

    assert stations_result["type"] == FlowResultType.CREATE_ENTRY
    assert stations_result["title"] == config_entry.title
    assert stations_result["data"] == config_entry.data
    assert len(mock_setup_entry.mock_calls) == 1


async def test_no_station_found(
    hass: HomeAssistant,
    aioambient: AsyncMock,
    open_api: OpenAPI,
) -> None:
    """Test that we abort when we cannot find a station in the area."""

    setup_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert setup_result["type"] == FlowResultType.FORM
    assert setup_result["step_id"] == "user"

    with patch.object(
        open_api,
        "get_devices_by_location",
        AsyncMock(return_value=[]),
    ):
        user_result = await hass.config_entries.flow.async_configure(
            setup_result["flow_id"],
            {"location": {"latitude": 10.0, "longitude": 20.0, "radius": 1.0}},
        )

    assert user_result["type"] == FlowResultType.FORM
    assert user_result["step_id"] == "user"
    assert user_result["errors"] == {"base": "no_stations_found"}
