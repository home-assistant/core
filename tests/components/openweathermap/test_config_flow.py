"""Define tests for the OpenWeatherMap config flow."""
from asynctest import MagicMock, patch

from homeassistant import data_entry_flow
from homeassistant.components.openweathermap.const import (
    CONF_LANGUAGE,
    DEFAULT_FORECAST_MODE,
    DEFAULT_LANGUAGE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
)

from tests.common import MockConfigEntry

CONFIG = {
    CONF_NAME: "openweathermap",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 50,
    CONF_LONGITUDE: 40,
    CONF_MODE: DEFAULT_FORECAST_MODE,
    CONF_LANGUAGE: DEFAULT_LANGUAGE,
    CONF_MONITORED_CONDITIONS: "",
}


async def test_form(hass):
    """Test that the form is served with valid input."""
    mocked_owm = _create_mocked_owm(True)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONFIG[CONF_NAME]
        assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
        assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
        assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]


async def test_options_form(hass):
    """Test that the options form."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="openweathermap_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    mocked_owm = _create_mocked_owm(True)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_MODE: "daily"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {
            CONF_MODE: "daily",
            CONF_MONITORED_CONDITIONS: "",
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
        }


async def test_invalid_api_key(hass):
    """Test that the form is served with no input."""
    mocked_owm = _create_mocked_owm(False)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "auth"}


async def test_invalid_monitored_conditions(hass):
    """Test that the form is served with no input."""
    mocked_owm = _create_mocked_owm(True)
    CONFIG[CONF_MONITORED_CONDITIONS] = "test"

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "monitored_conditions"}


def _create_mocked_owm(is_api_online: bool):
    mocked_owm = MagicMock()
    type(mocked_owm).is_API_online = MagicMock(return_value=is_api_online)
    return mocked_owm
