"""Tests for the Elgato Key Light config flow."""
import aiohttp

from homeassistant import data_entry_flow
from homeassistant.components.elgato.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.get(
        "http://127.0.0.1:9123/elgato/accessory-info",
        text=load_fixture("elgato/info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    # Start a discovered configuration flow, to guarantee a user flow doesn't abort
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data={
            "host": "127.0.0.1",
            "hostname": "example.local.",
            "port": 9123,
            "properties": {},
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 9123}
    )

    assert result["data"][CONF_HOST] == "127.0.0.1"
    assert result["data"][CONF_PORT] == 9123
    assert result["data"][CONF_SERIAL_NUMBER] == "CN11A1A00001"
    assert result["title"] == "CN11A1A00001"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].unique_id == "CN11A1A00001"


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the zeroconf flow from start to finish."""
    aioclient_mock.get(
        "http://127.0.0.1:9123/elgato/accessory-info",
        text=load_fixture("elgato/info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data={
            "host": "127.0.0.1",
            "hostname": "example.local.",
            "port": 9123,
            "properties": {},
        },
    )

    assert result["description_placeholders"] == {CONF_SERIAL_NUMBER: "CN11A1A00001"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0]["flow_id"] == result["flow_id"]
    assert progress[0]["context"]["confirm_only"] is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["data"][CONF_HOST] == "127.0.0.1"
    assert result["data"][CONF_PORT] == 9123
    assert result["data"][CONF_SERIAL_NUMBER] == "CN11A1A00001"
    assert result["title"] == "CN11A1A00001"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on Elgato Key Light connection error."""
    aioclient_mock.get(
        "http://127.0.0.1/elgato/accessory-info", exc=aiohttp.ClientError
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 9123},
    )

    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zeroconf_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on Elgato Key Light connection error."""
    aioclient_mock.get(
        "http://127.0.0.1/elgato/accessory-info", exc=aiohttp.ClientError
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"host": "127.0.0.1", "port": 9123},
    )

    assert result["reason"] == "cannot_connect"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if Elgato Key Light device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 9123},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if Elgato Key Light device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data={"host": "127.0.0.1", "port": 9123},
    )

    assert result["reason"] == "already_configured"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data={"host": "127.0.0.2", "port": 9123},
    )

    assert result["reason"] == "already_configured"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].data[CONF_HOST] == "127.0.0.2"
