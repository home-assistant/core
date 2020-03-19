"""Tests for the WLED config flow."""
import aiohttp

from homeassistant import data_entry_flow
from homeassistant.components.wled import config_flow
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zeroconf_confirm_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""
    flow = config_flow.WLEDFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF, CONF_NAME: "test"}
    result = await flow.async_step_zeroconf_confirm()

    assert result["description_placeholders"] == {CONF_NAME: "test"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zerconf_form(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the zeroconf confirmation form is served."""
    aioclient_mock.get(
        "http://example.local:80/json/",
        text=load_fixture("wled/rgb.json"),
        headers={"Content-Type": "application/json"},
    )

    flow = config_flow.WLEDFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF}
    result = await flow.async_step_zeroconf(
        {"hostname": "example.local.", "properties": {}}
    )

    assert flow.context[CONF_HOST] == "example.local"
    assert flow.context[CONF_NAME] == "example"
    assert result["description_placeholders"] == {CONF_NAME: "example"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on WLED connection error."""
    aioclient_mock.get("http://example.com/json/", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "example.com"},
    )

    assert result["errors"] == {"base": "connection_error"}
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zeroconf_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on WLED connection error."""
    aioclient_mock.get("http://example.local/json/", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"hostname": "example.local.", "properties": {}},
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_confirm_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on WLED connection error."""
    aioclient_mock.get("http://example.com/json/", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={
            "source": SOURCE_ZEROCONF,
            CONF_HOST: "example.com",
            CONF_NAME: "test",
        },
        data={"hostname": "example.com.", "properties": {}},
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_no_data(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort if zeroconf provides no data."""
    flow = config_flow.WLEDFlowHandler()
    flow.hass = hass
    result = await flow.async_step_zeroconf()

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "example.local"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"hostname": "example.local.", "properties": {}},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_with_mac_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"hostname": "example.local.", "properties": {CONF_MAC: "aabbccddeeff"}},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.get(
        "http://example.local:80/json/",
        text=load_fixture("wled/rgb.json"),
        headers={"Content-Type": "application/json"},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "example.local"}
    )

    assert result["data"][CONF_HOST] == "example.local"
    assert result["data"][CONF_MAC] == "aabbccddeeff"
    assert result["title"] == "example.local"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.get(
        "http://example.local:80/json/",
        text=load_fixture("wled/rgb.json"),
        headers={"Content-Type": "application/json"},
    )

    flow = config_flow.WLEDFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF}
    result = await flow.async_step_zeroconf(
        {"hostname": "example.local.", "properties": {}}
    )

    assert flow.context[CONF_HOST] == "example.local"
    assert flow.context[CONF_NAME] == "example"
    assert result["description_placeholders"] == {CONF_NAME: "example"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await flow.async_step_zeroconf_confirm(
        user_input={CONF_HOST: "example.local"}
    )
    assert result["data"][CONF_HOST] == "example.local"
    assert result["data"][CONF_MAC] == "aabbccddeeff"
    assert result["title"] == "example"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
