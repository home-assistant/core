"""Test the PubliBike config flow."""
from unittest.mock import MagicMock, patch

from requests import ConnectionError as ConnErr

from homeassistant import config_entries
from homeassistant.components.publibike import (
    BATTERY_LIMIT,
    DOMAIN,
    LATITUDE,
    LONGITUDE,
    STATION_ID,
)

TEST_CONF = {
    STATION_ID: 123,
    BATTERY_LIMIT: 99,
    LATITUDE: 1.0,
    LONGITUDE: 1.0,
}


async def test_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.publibike.PubliBike.getStations",
        return_value=[MagicMock(stationId=123)],
    ), patch(
        "homeassistant.components.publibike.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "PubliBike"
    assert result2["data"] == {
        "station_id": 123,
        "battery_limit": 99,
        "latitude": 1.0,
        "longitude": 1.0,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_id(hass):
    """Test we handle an invalid station id."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("homeassistant.components.publibike.PubliBike.getStations"), patch(
        "homeassistant.components.publibike.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_id"}


async def test_form_connection_error(hass):
    """Test we handle connection errors."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.publibike.PubliBike.getStations",
        side_effect=ConnErr(),
    ), patch(
        "homeassistant.components.publibike.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "connection_error"}


async def test_form_unknown_error(hass):
    """Test we handle unknown errors."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.publibike.PubliBike.getStations",
        side_effect=ValueError("Some other error"),
    ), patch(
        "homeassistant.components.publibike.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
