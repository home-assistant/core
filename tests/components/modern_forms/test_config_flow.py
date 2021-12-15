"""Tests for the Modern Forms config flow."""
from unittest.mock import MagicMock, patch

import aiohttp
from aiomodernforms import ModernFormsConnectionError

from homeassistant.components import zeroconf
from homeassistant.components.modern_forms.const import DOMAIN
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
    aioclient_mock.post(
        "http://192.168.1.123:80/mf",
        text=load_fixture("modern_forms/device_info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    with patch(
        "homeassistant.components.modern_forms.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
        )

    assert result2.get("title") == "ModernFormsFan"
    assert "data" in result2
    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"][CONF_HOST] == "192.168.1.123"
    assert result2["data"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.post(
        "http://192.168.1.123:80/mf",
        text=load_fixture("modern_forms/device_info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
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
    assert result2["data"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"


@patch(
    "homeassistant.components.modern_forms.ModernFormsDevice.update",
    side_effect=ModernFormsConnectionError,
)
async def test_connection_error(
    update_mock: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on Modern Forms connection error."""
    aioclient_mock.post("http://example.com/mf", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "example.com"},
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


@patch(
    "homeassistant.components.modern_forms.ModernFormsDevice.update",
    side_effect=ModernFormsConnectionError,
)
async def test_zeroconf_connection_error(
    update_mock: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on Modern Forms connection error."""
    aioclient_mock.post("http://192.168.1.123/mf", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "cannot_connect"


@patch(
    "homeassistant.components.modern_forms.ModernFormsDevice.update",
    side_effect=ModernFormsConnectionError,
)
async def test_zeroconf_confirm_connection_error(
    update_mock: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on Modern Forms connection error."""
    aioclient_mock.post("http://192.168.1.123:80/mf", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_ZEROCONF,
            CONF_HOST: "example.com",
            CONF_NAME: "test",
        },
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.com.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "cannot_connect"


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if Modern Forms device already configured."""
    aioclient_mock.post(
        "http://192.168.1.123:80/mf",
        text=load_fixture("modern_forms/device_info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    await init_integration(hass, aioclient_mock, skip_setup=True)

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            "host": "192.168.1.123",
            "hostname": "example.local.",
            "properties": {CONF_MAC: "AA:BB:CC:DD:EE:FF"},
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            "host": "192.168.1.123",
            "hostname": "example.local.",
            "properties": {CONF_MAC: "AA:BB:CC:DD:EE:FF"},
        },
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_with_mac_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if a Modern Forms device already configured."""
    await init_integration(hass, aioclient_mock, skip_setup=True)

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            "host": "192.168.1.123",
            "hostname": "example.local.",
            "properties": {CONF_MAC: "AA:BB:CC:DD:EE:FF"},
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "AA:BB:CC:DD:EE:FF"},
            type="mock_type",
        ),
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"
