"""Tests for the here_weather config_flow."""
import herepy
import pytest

from homeassistant.components.here_weather.const import (
    CONF_API_KEY,
    CONF_LOCATION_NAME,
    CONF_OPTION,
    CONF_OPTION_COORDINATES,
    CONF_OPTION_LOCATION_NAME,
    CONF_OPTION_ZIP_CODE,
    CONF_ZIP_CODE,
    DAILY_SIMPLE_ATTRIBUTES,
    DEFAULT_MODE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
    EVENT_HOMEASSISTANT_START,
)

from .const import daily_simple_forecasts_response

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "conf_option, method_to_patch, conf_updates",
    [
        (
            CONF_OPTION_COORDINATES,
            "herepy.DestinationWeatherApi.weather_for_coordinates",
            {CONF_LATITUDE: "40.79962", CONF_LONGITUDE: "-73.970314"},
        ),
        (
            CONF_OPTION_ZIP_CODE,
            "herepy.DestinationWeatherApi.weather_for_zip_code",
            {CONF_ZIP_CODE: "test"},
        ),
        (
            CONF_OPTION_LOCATION_NAME,
            "herepy.DestinationWeatherApi.weather_for_location_name",
            {CONF_LOCATION_NAME: "test"},
        ),
    ],
)
async def test_config_flow(hass, conf_option, method_to_patch, conf_updates):
    """Test we can finish a config flow."""
    with patch(
        method_to_patch, return_value=daily_simple_forecasts_response,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OPTION: conf_option}
        )
        assert result["type"] == "form"
        config = {
            CONF_API_KEY: "test",
            CONF_NAME: DOMAIN,
            CONF_MODE: DEFAULT_MODE,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        }
        config.update(conf_updates)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        assert result["type"] == "create_entry"

        await hass.async_block_till_done()
        state = hass.states.get("sensor.here_weather_low_temperature")
        assert state


@pytest.mark.parametrize(
    "conf_option, method_to_patch, conf_updates",
    [
        (
            CONF_OPTION_COORDINATES,
            "herepy.DestinationWeatherApi.weather_for_coordinates",
            {CONF_LATITUDE: "40.79962", CONF_LONGITUDE: "-73.970314"},
        ),
        (
            CONF_OPTION_ZIP_CODE,
            "herepy.DestinationWeatherApi.weather_for_zip_code",
            {CONF_ZIP_CODE: "test"},
        ),
        (
            CONF_OPTION_LOCATION_NAME,
            "herepy.DestinationWeatherApi.weather_for_location_name",
            {CONF_LOCATION_NAME: "test"},
        ),
    ],
)
async def test_unauthorized(hass, conf_option, method_to_patch, conf_updates):
    """Test handling of an unauthorized api key."""
    with patch(
        method_to_patch, side_effect=herepy.UnauthorizedError("Unauthorized"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OPTION: conf_option}
        )
        assert result["type"] == "form"
        config = {
            CONF_API_KEY: "test",
            CONF_NAME: DOMAIN,
            CONF_MODE: DEFAULT_MODE,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        }
        config.update(conf_updates)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "unauthorized"


@pytest.mark.parametrize(
    "conf_option, method_to_patch, conf_updates",
    [
        (
            CONF_OPTION_COORDINATES,
            "herepy.DestinationWeatherApi.weather_for_coordinates",
            {CONF_LATITUDE: "40.79962", CONF_LONGITUDE: "-73.970314"},
        ),
        (
            CONF_OPTION_ZIP_CODE,
            "herepy.DestinationWeatherApi.weather_for_zip_code",
            {CONF_ZIP_CODE: "test"},
        ),
        (
            CONF_OPTION_LOCATION_NAME,
            "herepy.DestinationWeatherApi.weather_for_location_name",
            {CONF_LOCATION_NAME: "test"},
        ),
    ],
)
async def test_invalid_request(hass, conf_option, method_to_patch, conf_updates):
    """Test handling of an invalid request."""
    with patch(
        method_to_patch, side_effect=herepy.InvalidRequestError("Invalid"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OPTION: conf_option}
        )
        assert result["type"] == "form"
        config = {
            CONF_API_KEY: "test",
            CONF_NAME: DOMAIN,
            CONF_MODE: DEFAULT_MODE,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        }
        config.update(conf_updates)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_request"


@pytest.mark.parametrize(
    "conf_option, method_to_patch, conf_updates",
    [
        (
            CONF_OPTION_COORDINATES,
            "herepy.DestinationWeatherApi.weather_for_coordinates",
            {CONF_LATITUDE: "40.79962", CONF_LONGITUDE: "-73.970314"},
        ),
        (
            CONF_OPTION_ZIP_CODE,
            "herepy.DestinationWeatherApi.weather_for_zip_code",
            {CONF_ZIP_CODE: "test"},
        ),
        (
            CONF_OPTION_LOCATION_NAME,
            "herepy.DestinationWeatherApi.weather_for_location_name",
            {CONF_LOCATION_NAME: "test"},
        ),
    ],
)
async def test_form_already_configured(
    hass, conf_option, method_to_patch, conf_updates
):
    """Test is already configured."""
    with patch(
        method_to_patch, return_value=daily_simple_forecasts_response,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OPTION: conf_option}
        )
        assert result["type"] == "form"
        config = {
            CONF_API_KEY: "test",
            CONF_NAME: DOMAIN,
            CONF_MODE: DEFAULT_MODE,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        }
        config.update(conf_updates)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        assert result["type"] == "create_entry"

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OPTION: conf_option}
        )
        assert result["type"] == "form"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_options(hass):
    """Test options for Kraken."""
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
                CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
            options={CONF_SCAN_INTERVAL: 60},
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: 10}
        )
        await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert result["data"][CONF_SCAN_INTERVAL] == 10


async def test_default_options(hass):
    """Test default options for Kraken."""
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
                CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
            options={CONF_SCAN_INTERVAL: 60},
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"
        assert result["step_id"] == "init"


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
                CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
            options={CONF_SCAN_INTERVAL: 60},
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == (len(DAILY_SIMPLE_ATTRIBUTES) + 1)
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0
