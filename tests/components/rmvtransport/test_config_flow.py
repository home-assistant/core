"""Tests for rmvtransport config flow."""
from unittest.mock import patch

from homeassistant.components.rmvtransport import config_flow
from tests.common import mock_coro

from .test_sensor import get_departures_mock, search_station_mock


async def test_flow_works(hass, aioclient_mock):
    """Test that config flow works."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "RMVtransport.RMVtransport.get_departures",
        return_value=mock_coro(get_departures_mock()),
    ):
        with patch(
            "RMVtransport.RMVtransport.search_station",
            return_value=mock_coro(search_station_mock()),
        ):

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={config_flow.CONF_STATION: "3000010"}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={"ICE": False, "IC": False, "RE": False, "EC": False},
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={config_flow.CONF_SHOW_ON_MAP: True}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )

    assert result["type"] == "create_entry"
    assert result["title"] == "Frankfurt (Main) Hauptbahnhof"
    assert result["data"][config_flow.CONF_STATION] == "3000010"
    assert result["data"][config_flow.CONF_SHOW_ON_MAP] is True
    assert result["data"][config_flow.CONF_PRODUCTS] == [
        "U-Bahn",
        "Tram",
        "Bus",
        "S",
        "RB",
    ]
