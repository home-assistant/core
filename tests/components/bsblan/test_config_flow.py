"""Tests for the BSBLan device config flow."""
import aiohttp

from homeassistant import data_entry_flow
from homeassistant.components.bsblan import config_flow
from homeassistant.components.bsblan.const import CONF_DEVICE_IDENT, CONF_PASSKEY
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on BSBLan connection error."""
    aioclient_mock.post(
        "http://example.local:80/1234/JQ?Parameter=6224,6225,6226",
        exc=aiohttp.ClientError,
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "example.local",
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
            CONF_PASSKEY: "1234",
            CONF_PORT: 80,
        },
    )

    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if BSBLan device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "example.local",
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
            CONF_PASSKEY: "1234",
            CONF_PORT: 80,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.post(
        "http://example.local:80/1234/JQ?Parameter=6224,6225,6226",
        text=load_fixture("bsblan/info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "example.local",
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
            CONF_PASSKEY: "1234",
            CONF_PORT: 80,
        },
    )

    assert result["data"][CONF_HOST] == "example.local"
    assert result["data"][CONF_USERNAME] == "nobody"
    assert result["data"][CONF_PASSWORD] == "qwerty"
    assert result["data"][CONF_PASSKEY] == "1234"
    assert result["data"][CONF_PORT] == 80
    assert result["data"][CONF_DEVICE_IDENT] == "RVS21.831F/127"
    assert result["title"] == "RVS21.831F/127"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    entries = hass.config_entries.async_entries(config_flow.DOMAIN)
    assert entries[0].unique_id == "RVS21.831F/127"


async def test_full_user_flow_implementation_without_auth(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.post(
        "http://example2.local:80/JQ?Parameter=6224,6225,6226",
        text=load_fixture("bsblan/info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "example2.local",
            CONF_PORT: 80,
        },
    )

    assert result["data"][CONF_HOST] == "example2.local"
    assert result["data"][CONF_USERNAME] is None
    assert result["data"][CONF_PASSWORD] is None
    assert result["data"][CONF_PASSKEY] is None
    assert result["data"][CONF_PORT] == 80
    assert result["data"][CONF_DEVICE_IDENT] == "RVS21.831F/127"
    assert result["title"] == "RVS21.831F/127"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    entries = hass.config_entries.async_entries(config_flow.DOMAIN)
    assert entries[0].unique_id == "RVS21.831F/127"
