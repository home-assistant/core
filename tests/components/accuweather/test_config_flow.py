"""Define tests for the AccuWeather config flow."""
from unittest.mock import PropertyMock, patch

from accuweather import ApiError, InvalidApiKeyError, RequestsExceededError

from homeassistant import data_entry_flow
from homeassistant.components.accuweather.const import CONF_FORECAST, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

VALID_CONFIG = {
    CONF_NAME: "abcd",
    CONF_API_KEY: "32-character-string-1234567890qw",
    CONF_LATITUDE: 55.55,
    CONF_LONGITUDE: 122.12,
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_api_key_too_short(hass: HomeAssistant) -> None:
    """Test that errors are shown when API key is too short."""
    # The API key length check is done by the library without polling the AccuWeather
    # server so we don't need to patch the library method.
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


async def test_invalid_api_key(hass: HomeAssistant) -> None:
    """Test that errors are shown when API key is invalid."""
    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        side_effect=InvalidApiKeyError("Invalid API key"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_api_error(hass: HomeAssistant) -> None:
    """Test API error."""
    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        side_effect=ApiError("Invalid response from AccuWeather API"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_requests_exceeded_error(hass: HomeAssistant) -> None:
    """Test requests exceeded error."""
    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        side_effect=RequestsExceededError(
            "The allowed number of requests has been exceeded"
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {CONF_API_KEY: "requests_exceeded"}


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        return_value=load_json_object_fixture("accuweather/location_data.json"),
    ):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="123456",
            data=VALID_CONFIG,
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "single_instance_allowed"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        return_value=load_json_object_fixture("accuweather/location_data.json"),
    ), patch(
        "homeassistant.components.accuweather.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "abcd"
        assert result["data"][CONF_NAME] == "abcd"
        assert result["data"][CONF_LATITUDE] == 55.55
        assert result["data"][CONF_LONGITUDE] == 122.12
        assert result["data"][CONF_API_KEY] == "32-character-string-1234567890qw"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        data=VALID_CONFIG,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        return_value=load_json_object_fixture("accuweather/location_data.json"),
    ), patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
        return_value=load_json_object_fixture(
            "accuweather/current_conditions_data.json"
        ),
    ), patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_daily_forecast"
    ), patch(
        "homeassistant.components.accuweather.AccuWeather.requests_remaining",
        new_callable=PropertyMock,
        return_value=10,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_FORECAST: True}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options == {CONF_FORECAST: True}

        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
