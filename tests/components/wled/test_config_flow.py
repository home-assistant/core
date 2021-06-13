"""Tests for the WLED config flow."""
from unittest.mock import MagicMock, patch

import aiohttp
from wled import WLEDConnectionError

from homeassistant.components.wled.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import init_integration

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.get(
        "http://192.168.1.123:80/json/",
        text=load_fixture("wled/rgb.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("title") == "192.168.1.123"
    assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.123"
    assert result["data"][CONF_MAC] == "aabbccddeeff"


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.get(
        "http://192.168.1.123:80/json/",
        text=load_fixture("wled/rgb.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"host": "192.168.1.123", "hostname": "example.local.", "properties": {}},
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    assert result.get("description_placeholders") == {CONF_NAME: "example"}
    assert result.get("step_id") == "zeroconf_confirm"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    flow = flows[0]
    assert "context" in flow
    assert flow["context"][CONF_HOST] == "192.168.1.123"
    assert flow["context"][CONF_NAME] == "example"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2.get("title") == "example"
    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY

    assert "data" in result2
    assert result2["data"][CONF_HOST] == "192.168.1.123"
    assert result2["data"][CONF_MAC] == "aabbccddeeff"


@patch("homeassistant.components.wled.WLED.update", side_effect=WLEDConnectionError)
async def test_connection_error(
    update_mock: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on WLED connection error."""
    aioclient_mock.get("http://example.com/json/", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "example.com"},
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


@patch("homeassistant.components.wled.WLED.update", side_effect=WLEDConnectionError)
async def test_zeroconf_connection_error(
    update_mock: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on WLED connection error."""
    aioclient_mock.get("http://192.168.1.123/json/", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"host": "192.168.1.123", "hostname": "example.local.", "properties": {}},
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "cannot_connect"


@patch("homeassistant.components.wled.WLED.update", side_effect=WLEDConnectionError)
async def test_zeroconf_confirm_connection_error(
    update_mock: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on WLED connection error."""
    aioclient_mock.get("http://192.168.1.123:80/json/", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_ZEROCONF,
            CONF_HOST: "example.com",
            CONF_NAME: "test",
        },
        data={"host": "192.168.1.123", "hostname": "example.com.", "properties": {}},
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "cannot_connect"


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.123"},
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"host": "192.168.1.123", "hostname": "example.local.", "properties": {}},
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_with_mac_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "host": "192.168.1.123",
            "hostname": "example.local.",
            "properties": {CONF_MAC: "aabbccddeeff"},
        },
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"
