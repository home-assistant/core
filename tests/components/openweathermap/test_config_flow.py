"""Define tests for the OpenWeatherMap config flow."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from pyopenweathermap import (
    CurrentWeather,
    DailyTemperature,
    DailyWeatherForecast,
    RequestError,
    WeatherCondition,
    WeatherReport,
)
import pytest

from homeassistant.components.openweathermap.const import (
    DEFAULT_LANGUAGE,
    DEFAULT_OWM_MODE,
    DOMAIN,
    OWM_MODE_V25,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG = {
    CONF_NAME: "openweathermap",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 50,
    CONF_LONGITUDE: 40,
    CONF_LANGUAGE: DEFAULT_LANGUAGE,
    CONF_MODE: OWM_MODE_V25,
}

VALID_YAML_CONFIG = {CONF_API_KEY: "foo"}


def _create_mocked_owm_factory(is_valid: bool):
    current_weather = CurrentWeather(
        date_time=datetime.fromtimestamp(1714063536, tz=UTC),
        temperature=6.84,
        feels_like=2.07,
        pressure=1000,
        humidity=82,
        dew_point=3.99,
        uv_index=0.13,
        cloud_coverage=75,
        visibility=10000,
        wind_speed=9.83,
        wind_bearing=199,
        wind_gust=None,
        rain={},
        snow={},
        condition=WeatherCondition(
            id=803,
            main="Clouds",
            description="broken clouds",
            icon="04d",
        ),
    )
    daily_weather_forecast = DailyWeatherForecast(
        date_time=datetime.fromtimestamp(1714063536, tz=UTC),
        summary="There will be clear sky until morning, then partly cloudy",
        temperature=DailyTemperature(
            day=18.76,
            min=8.11,
            max=21.26,
            night=13.06,
            evening=20.51,
            morning=8.47,
        ),
        feels_like=DailyTemperature(
            day=18.76,
            min=8.11,
            max=21.26,
            night=13.06,
            evening=20.51,
            morning=8.47,
        ),
        pressure=1015,
        humidity=62,
        dew_point=11.34,
        wind_speed=8.14,
        wind_bearing=168,
        wind_gust=11.81,
        condition=WeatherCondition(
            id=803,
            main="Clouds",
            description="broken clouds",
            icon="04d",
        ),
        cloud_coverage=84,
        precipitation_probability=0,
        uv_index=4.06,
        rain=0,
        snow=0,
    )
    weather_report = WeatherReport(current_weather, [], [daily_weather_forecast])

    mocked_owm_client = MagicMock()
    mocked_owm_client.validate_key = AsyncMock(return_value=is_valid)
    mocked_owm_client.get_weather = AsyncMock(return_value=weather_report)

    return mocked_owm_client


@pytest.fixture(name="owm_client_mock")
def mock_owm_client():
    """Mock config_flow OWMClient."""
    with patch(
        "homeassistant.components.openweathermap.create_owm_client",
    ) as mock:
        yield mock


@pytest.fixture(name="config_flow_owm_client_mock")
def mock_config_flow_owm_client():
    """Mock config_flow OWMClient."""
    with patch(
        "homeassistant.components.openweathermap.utils.create_owm_client",
    ) as mock:
        yield mock


async def test_successful_config_flow(
    hass: HomeAssistant,
    owm_client_mock,
    config_flow_owm_client_mock,
) -> None:
    """Test that the form is served with valid input."""
    mock = _create_mocked_owm_factory(True)
    owm_client_mock.return_value = mock
    config_flow_owm_client_mock.return_value = mock

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    entry = conf_entries[0]
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG[CONF_NAME]
    assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]


async def test_abort_config_flow(
    hass: HomeAssistant,
    owm_client_mock,
    config_flow_owm_client_mock,
) -> None:
    """Test that the form is served with same data."""
    mock = _create_mocked_owm_factory(True)
    owm_client_mock.return_value = mock
    config_flow_owm_client_mock.return_value = mock

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT


async def test_config_flow_options_change(
    hass: HomeAssistant,
    owm_client_mock,
    config_flow_owm_client_mock,
) -> None:
    """Test that the options form."""
    mock = _create_mocked_owm_factory(True)
    owm_client_mock.return_value = mock
    config_flow_owm_client_mock.return_value = mock

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="openweathermap_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_language = "es"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_MODE: DEFAULT_OWM_MODE, CONF_LANGUAGE: new_language},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_LANGUAGE: new_language,
        CONF_MODE: DEFAULT_OWM_MODE,
    }

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    updated_language = "es"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_LANGUAGE: updated_language}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_LANGUAGE: updated_language,
        CONF_MODE: DEFAULT_OWM_MODE,
    }

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_form_invalid_api_key(
    hass: HomeAssistant,
    config_flow_owm_client_mock,
) -> None:
    """Test that the form is served with no input."""
    config_flow_owm_client_mock.return_value = _create_mocked_owm_factory(False)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_api_key"}

    config_flow_owm_client_mock.return_value = _create_mocked_owm_factory(True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_api_call_error(
    hass: HomeAssistant,
    config_flow_owm_client_mock,
) -> None:
    """Test setting up with api call error."""
    config_flow_owm_client_mock.return_value = _create_mocked_owm_factory(True)
    config_flow_owm_client_mock.side_effect = RequestError("oops")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    config_flow_owm_client_mock.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
