"""Define tests for the Sanix config flow."""
from http import HTTPStatus

from sanix.exceptions import SanixException

from homeassistant import data_entry_flow
from homeassistant.components.sanix.const import (
    CONF_SERIAL_NO,
    CONF_TOKEN,
    DOMAIN,
    MANUFACTURER,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import API_URL

from tests.common import MockConfigEntry, load_fixture, patch
from tests.test_util.aiohttp import AiohttpClientMocker

CONFIG = {CONF_SERIAL_NO: "1810088", CONF_TOKEN: "75868dcf8ea4c64e2063f6c4e70132d2"}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_unauthorized(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors are shown when user was not authorized."""
    aioclient_mock.get(API_URL, text=load_fixture("unauthorized.json", "sanix"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["errors"] == {"base": "unauthorized"}


async def test_bad_request(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors are shown when something went wrong while requesting the Sanix API."""
    aioclient_mock.get(
        API_URL, exc=SanixException(HTTPStatus.BAD_REQUEST, "Something went wrong")
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["errors"] == {"base": "bad_request"}


async def test_duplicate_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors are shown when duplicates are added."""
    aioclient_mock.get(API_URL, text=load_fixture("authorized.json", "sanix"))
    MockConfigEntry(domain=DOMAIN, unique_id="1810088", data=CONFIG).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_create_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the user step works."""
    aioclient_mock.get(API_URL, text=load_fixture("authorized.json", "sanix"))

    with patch("homeassistant.components.sanix.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{MANUFACTURER.upper()}-{CONFIG[CONF_SERIAL_NO]}"
    assert result["data"][CONF_TOKEN] == CONFIG[CONF_TOKEN]
