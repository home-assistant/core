"""Tests for the here_weather config_flow."""
import herepy

from homeassistant.components.here_weather.const import (
    DAILY_SIMPLE_ATTRIBUTES,
    DEFAULT_MODE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_START,
)

from .const import daily_simple_forecasts_response

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_config_flow(hass):
    """Test we can finish a config flow."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        return_value=daily_simple_forecasts_response,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        config = {
            CONF_API_KEY: "test",
            CONF_NAME: DOMAIN,
            CONF_MODE: DEFAULT_MODE,
            CONF_LATITUDE: "40.79962",
            CONF_LONGITUDE: "-73.970314",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        assert result["type"] == "create_entry"

        await hass.async_block_till_done()
        state = hass.states.get("sensor.here_weather_low_temperature")
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
            CONF_MODE: DEFAULT_MODE,
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
            CONF_MODE: DEFAULT_MODE,
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
        return_value=daily_simple_forecasts_response,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_MODE: DEFAULT_MODE,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_SCAN_INTERVAL: 10},
        )
        await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert result["data"][CONF_SCAN_INTERVAL] == 10


async def test_unload_entry(hass):
    """Test unloading a config entry removes all entities."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        return_value=daily_simple_forecasts_response,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_MODE: DEFAULT_MODE,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == (len(DAILY_SIMPLE_ATTRIBUTES))
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0
