"""Define tests for the Airly config flow."""
from http import HTTPStatus

from airly.exceptions import AirlyError

from homeassistant import data_entry_flow
from homeassistant.components.airly.const import CONF_USE_NEAREST, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from . import API_NEAREST_URL, API_POINT_URL

from tests.common import MockConfigEntry, load_fixture, patch
from tests.test_util.aiohttp import AiohttpClientMocker

CONFIG = {
    CONF_NAME: "Home",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 123,
    CONF_LONGITUDE: 456,
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_invalid_api_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors are shown when API key is invalid."""
    aioclient_mock.get(
        API_POINT_URL,
        exc=AirlyError(
            HTTPStatus.UNAUTHORIZED, {"message": "Invalid authentication credentials"}
        ),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["errors"] == {"base": "invalid_api_key"}


async def test_invalid_location(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors are shown when location is invalid."""
    aioclient_mock.get(API_POINT_URL, text=load_fixture("no_station.json", "airly"))

    aioclient_mock.get(
        API_NEAREST_URL,
        exc=AirlyError(HTTPStatus.NOT_FOUND, {"message": "Installation was not found"}),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["errors"] == {"base": "wrong_location"}


async def test_invalid_location_for_point_and_nearest(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an abort when the location is wrong for the point and nearest methods."""

    aioclient_mock.get(API_POINT_URL, text=load_fixture("no_station.json", "airly"))

    aioclient_mock.get(API_NEAREST_URL, text=load_fixture("no_station.json", "airly"))

    with patch("homeassistant.components.airly.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "wrong_location"


async def test_duplicate_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors are shown when duplicates are added."""
    aioclient_mock.get(API_POINT_URL, text=load_fixture("valid_station.json", "airly"))
    MockConfigEntry(domain=DOMAIN, unique_id="123-456", data=CONFIG).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_create_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the user step works."""
    aioclient_mock.get(API_POINT_URL, text=load_fixture("valid_station.json", "airly"))

    with patch("homeassistant.components.airly.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG[CONF_NAME]
    assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]
    assert result["data"][CONF_USE_NEAREST] is False


async def test_create_entry_with_nearest_method(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the user step works with nearest method."""

    aioclient_mock.get(API_POINT_URL, text=load_fixture("no_station.json", "airly"))

    aioclient_mock.get(
        API_NEAREST_URL, text=load_fixture("valid_station.json", "airly")
    )

    with patch("homeassistant.components.airly.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG[CONF_NAME]
    assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]
    assert result["data"][CONF_USE_NEAREST] is True
