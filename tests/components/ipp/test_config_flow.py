"""Tests for the IPP config flow."""
import aiohttp

from homeassistant import data_entry_flow
from homeassistant.components.ipp import config_flow
from homeassistant.components.ipp.const import CONF_BASE_PATH, CONF_UUID
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from . import init_integration, load_fixture_binary

from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURE_USER_INPUT = {
    CONF_HOST: "EPSON123456.local",
    CONF_PORT: 361,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
    CONF_BASE_PATH: "/ipp/print",
}


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zeroconf_confirm_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""
    flow = config_flow.IPPFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF, CONF_NAME: "EPSON123456"}
    result = await flow.async_step_zeroconf_confirm()

    assert result["description_placeholders"] == {CONF_NAME: "EPSON123456"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zerconf_form(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the zeroconf confirmation form is served."""
    aioclient_mock.post(
        "http://EPSON123456.local:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    flow = config_flow.IPPFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF}
    result = await flow.async_step_zeroconf(
        {
            "hostname": "EPSON123456.local.",
            "port": 631,
            "properties": {"rp": "ipp/print"},
        }
    )

    assert flow.context[CONF_HOST] == "EPSON123456.local"
    assert flow.context[CONF_NAME] == "EPSON123456"
    assert result["description_placeholders"] == {CONF_NAME: "EPSON123456"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on IPP connection error."""
    aioclient_mock.post(
        "http://EPSON123456.local:631/ipp/print", exc=aiohttp.ClientError
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": SOURCE_USER}, data=FIXTURE_USER_INPUT,
    )

    assert result["errors"] == {"base": "connection_error"}
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zeroconf_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on IPP connection error."""
    aioclient_mock.post("http://EPSON123456.local/ipp/print", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "hostname": "EPSON123456.local.",
            "port": 631,
            "properties": {"rp": "ipp/print"},
        },
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_confirm_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on IPP connection error."""
    aioclient_mock.post("http://EPSON123456.local/ipp/print", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={
            "source": SOURCE_ZEROCONF,
            CONF_HOST: "EPSON123456.local",
            CONF_NAME: "EPSON123456",
        },
        data={
            "hostname": "EPSON123456.local.",
            "port": 631,
            "properties": {"rp": "ipp/print"},
        },
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_no_data(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort if zeroconf provides no data."""
    flow = config_flow.IPPFlowHandler()
    flow.hass = hass
    result = await flow.async_step_zeroconf()

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort user flow if printer already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": SOURCE_USER}, data=FIXTURE_USER_INPUT,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if printer already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "hostname": "EPSON123456.local.",
            "port": 631,
            "properties": {"rp": "ipp/print"},
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_with_uuid_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if printer already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "hostname": "EPSON123456.local.",
            "port": 631,
            "properties": {
                "rp": "ipp/print",
                "UUID": "cfe92100-67c4-11d4-a45f-f8d027761251",
            },
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.post(
        "http://EPSON123456.local:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "EPSON123456.local", CONF_BASE_PATH: "/ipp/print"},
    )

    assert result["data"][CONF_HOST] == "EPSON123456.local"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"
    assert result["title"] == "EPSON123456.local"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.post(
        "https://EPSON123456.local:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    flow = config_flow.IPPFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF}
    result = await flow.async_step_zeroconf(
        {
            "hostname": "EPSON123456.local.",
            "port": 631,
            "properties": {"rp": "ipp/print", "TLS": "1.2"},
        }
    )

    assert flow.context[CONF_HOST] == "EPSON123456.local"
    assert flow.context[CONF_NAME] == "EPSON123456"
    assert result["description_placeholders"] == {CONF_NAME: "EPSON123456"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await flow.async_step_zeroconf_confirm(
        user_input={CONF_HOST: "EPSON123456.local"}
    )
    assert result["data"][CONF_HOST] == "EPSON123456.local"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"
    assert result["data"][CONF_SSL]
    assert result["title"] == "EPSON123456"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
