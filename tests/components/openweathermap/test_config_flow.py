"""Define tests for the OpenWeatherMap config flow."""
from asynctest import MagicMock, patch
from pyowm.exceptions.api_call_error import APICallError
from pyowm.exceptions.api_response_error import UnauthorizedError

from homeassistant import data_entry_flow
from homeassistant.components.openweathermap.const import (
    CONF_LANGUAGE,
    DEFAULT_FORECAST_MODE,
    DEFAULT_LANGUAGE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
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
}

VALID_YAML_CONFIG = {CONF_API_KEY: "foo"}


async def test_form(hass):
    """Test that the form is served with valid input."""
    mocked_owm = _create_mocked_owm(True)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ), patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_refresh",
        _async_refresh,
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

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state == "loaded"

        await hass.config_entries.async_unload(conf_entries[0].entry_id)
        await hass.async_block_till_done()
        assert entry.state == "not_loaded"

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONFIG[CONF_NAME]
        assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
        assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
        assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]


async def test_form_import(hass):
    """Test we can import yaml config."""
    mocked_owm = _create_mocked_owm(True)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ), patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_refresh",
        _async_refresh,
    ), patch(
        "homeassistant.components.openweathermap.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.openweathermap.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=VALID_YAML_CONFIG.copy(),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_LATITUDE] == hass.config.latitude
        assert result["data"][CONF_LONGITUDE] == hass.config.longitude
        assert result["data"][CONF_API_KEY] == VALID_YAML_CONFIG[CONF_API_KEY]

        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_options(hass):
    """Test that the options form."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="openweathermap_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    mocked_owm = _create_mocked_owm(True)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ), patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_refresh",
        _async_refresh,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == "loaded"

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ), patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_refresh",
        _async_refresh,
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
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
        }

        await hass.async_block_till_done()

        assert config_entry.state == "loaded"

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_MODE: "freedaily"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {
            CONF_MODE: "freedaily",
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
        }

        await hass.async_block_till_done()

        assert config_entry.state == "setup_retry"


async def test_form_invalid_api_key(hass):
    """Test that the form is served with no input."""
    mocked_owm = _create_mocked_owm(True)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
        side_effect=UnauthorizedError(""),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "auth"}


async def test_form_api_call_error(hass):
    """Test setting up with api call error."""
    mocked_owm = _create_mocked_owm(True)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
        side_effect=APICallError(""),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "connection"}


async def test_form_api_offline(hass):
    """Test setting up with api call error."""
    mocked_owm = _create_mocked_owm(False)

    with patch(
        "homeassistant.components.openweathermap.config_flow.OWM",
        return_value=mocked_owm,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "auth"}


def _create_mocked_owm(is_api_online: bool):
    mocked_owm = MagicMock()
    mocked_owm.is_API_online = MagicMock(return_value=is_api_online)
    return mocked_owm


async def _async_refresh(self):
    return {}
