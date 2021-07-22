"""Tests for the here_weather config_flow."""
from unittest.mock import patch

import herepy

from homeassistant import config_entries, setup
from homeassistant.components.here_weather.const import DOMAIN, HERE_API_KEYS
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant

from . import mock_weather_for_coordinates

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        return_value=None,
    ), patch(
        "homeassistant.components.here_weather.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == DOMAIN
    assert result2["data"] == {
        CONF_API_KEY: "test",
        CONF_NAME: DOMAIN,
        CONF_LATITUDE: 40.79962,
        CONF_LONGITUDE: -73.970314,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_known_api_key(hass):
    """Test we can finish a config flow."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        side_effect=mock_weather_for_coordinates,
    ):
        hass.data.setdefault(HERE_API_KEYS, []).append("test")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        config = {
            CONF_API_KEY: "test",
            CONF_NAME: DOMAIN,
            CONF_LATITUDE: "40.79962",
            CONF_LONGITUDE: "-73.970314",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        assert result["type"] == "create_entry"

        await hass.async_block_till_done()
        state = hass.states.get("weather.here_weather_forecast_7days_simple")
        assert state


async def test_unauthorized(hass):
    """Test handling of an unauthorized api key."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        side_effect=herepy.UnauthorizedError("Unauthorized"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        config = {
            CONF_API_KEY: "test",
            CONF_NAME: DOMAIN,
            CONF_LATITUDE: "40.79962",
            CONF_LONGITUDE: "-73.970314",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "unauthorized"


async def test_invalid_request(hass):
    """Test handling of an invalid request."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        side_effect=herepy.InvalidRequestError("Invalid"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        config = {
            CONF_API_KEY: "test",
            CONF_NAME: DOMAIN,
            CONF_LATITUDE: "40.79962",
            CONF_LONGITUDE: "-73.970314",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_request"


async def test_options(hass):
    """Test the options flow."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        side_effect=mock_weather_for_coordinates,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_SCAN_INTERVAL: 10},
        )
        await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert result["data"][CONF_SCAN_INTERVAL] == 10
