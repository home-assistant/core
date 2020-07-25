"""Define tests for the AccuWeather config flow."""
import json

from accuweather import ApiError, InvalidApiKeyError, RequestsExceededError

from homeassistant import data_entry_flow
from homeassistant.components.accuweather.const import CONF_FORECAST, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture

VALID_CONFIG = {
    CONF_NAME: "abcd",
    CONF_API_KEY: "32-character-string-1234567890qw",
    CONF_LATITUDE: 55.55,
    CONF_LONGITUDE: 122.12,
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_invalid_api_key_1(hass):
    """Test that errors are shown when API key is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_NAME: "abcd",
            CONF_API_KEY: "foo",
            CONF_LATITUDE: 55.55,
            CONF_LONGITUDE: 122.12,
        },
    )

    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_invalid_api_key_2(hass):
    """Test that errors are shown when API key is invalid."""
    with patch(
        "accuweather.AccuWeather._async_get_data",
        side_effect=InvalidApiKeyError("Invalid API key"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG,
        )

        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_api_error(hass):
    """Test API error."""
    with patch(
        "accuweather.AccuWeather._async_get_data",
        side_effect=ApiError("Invalid response from AccuWeather API"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_requests_exceeded_error(hass):
    """Test requests exceeded error."""
    with patch(
        "accuweather.AccuWeather._async_get_data",
        side_effect=RequestsExceededError(
            "The allowed number of requests has been exceeded"
        ),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG,
        )

        assert result["errors"] == {CONF_API_KEY: "requests_exceeded"}


async def test_integration_already_exists(hass):
    """Test we only allow a single config flow."""
    with patch(
        "accuweather.AccuWeather._async_get_data",
        return_value=json.loads(load_fixture("accuweather/location_data.json")),
    ):
        MockConfigEntry(
            domain=DOMAIN, unique_id="123456", data=VALID_CONFIG,
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "single_instance_allowed"


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch(
        "accuweather.AccuWeather._async_get_data",
        return_value=json.loads(load_fixture("accuweather/location_data.json")),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "abcd"
        assert result["data"][CONF_NAME] == "abcd"
        assert result["data"][CONF_LATITUDE] == 55.55
        assert result["data"][CONF_LONGITUDE] == 122.12
        assert result["data"][CONF_API_KEY] == "32-character-string-1234567890qw"


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="123456", data=VALID_CONFIG,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "accuweather.AccuWeather._async_get_data",
        return_value=json.loads(load_fixture("accuweather/location_data.json")),
    ), patch(
        "accuweather.AccuWeather.async_get_current_conditions",
        return_value=json.loads(
            load_fixture("accuweather/current_conditions_data.json")
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_FORECAST: True}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_FORECAST: True}
