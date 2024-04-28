"""Define tests for the OpenWeatherMap config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyopenweathermap import CurrentWeather, RequestError, WeatherReport
import pytest

from homeassistant.components.openweathermap.const import DEFAULT_LANGUAGE, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
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
}

VALID_YAML_CONFIG = {CONF_API_KEY: "foo"}


def _create_mocked_owm_client(is_valid: bool):
    current_weather = CurrentWeather(
        dt=1714063536,
        temp=6.84,
        feels_like=2.07,
        pressure=1000,
        humidity=82,
        dew_point=3.99,
        uvi=0.13,
        clouds=75,
        visibility=10000,
        wind_speed=9.83,
        wind_deg=199,
        weather=[
            {
                "id": 803,
                "main": "Clouds",
                "description": "broken clouds",
                "icon": "04d",
            }
        ],
    )
    weather_report = WeatherReport(current_weather, [], [])

    mocked_owm_client = MagicMock()
    mocked_owm_client.validate_key = AsyncMock(return_value=is_valid)
    mocked_owm_client.get_weather = AsyncMock(return_value=weather_report)

    return mocked_owm_client


@pytest.fixture(name="owm_client_mock")
def mock_owm_client():
    """Mock config_flow OWMClient."""
    with patch(
        "homeassistant.components.openweathermap.OWMClient",
    ) as owm_client_mock:
        yield owm_client_mock


@pytest.fixture(name="config_flow_owm_client_mock")
def mock_config_flow_owm_client():
    """Mock config_flow OWMClient."""
    with patch(
        "homeassistant.components.openweathermap.config_flow.OWMClient",
    ) as config_flow_owm_client_mock:
        yield config_flow_owm_client_mock


async def test_form(
    owm_client_mock, config_flow_owm_client_mock, hass: HomeAssistant
) -> None:
    """Test that the form is served with valid input."""
    mock = _create_mocked_owm_client(True)
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


async def test_form_options(
    owm_client_mock, config_flow_owm_client_mock, hass: HomeAssistant
) -> None:
    """Test that the options form."""
    mock = _create_mocked_owm_client(True)
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

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_LANGUAGE: DEFAULT_LANGUAGE,
    }

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_LANGUAGE: DEFAULT_LANGUAGE,
    }

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_form_invalid_api_key(
    config_flow_owm_client_mock, hass: HomeAssistant
) -> None:
    """Test that the form is served with no input."""
    config_flow_owm_client_mock.return_value = _create_mocked_owm_client(False)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["errors"] == {"base": "invalid_api_key"}


async def test_form_api_call_error(
    config_flow_owm_client_mock, hass: HomeAssistant
) -> None:
    """Test setting up with api call error."""
    config_flow_owm_client_mock.return_value = _create_mocked_owm_client(True)
    config_flow_owm_client_mock.side_effect = RequestError("oops")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["errors"] == {"base": "cannot_connect"}
