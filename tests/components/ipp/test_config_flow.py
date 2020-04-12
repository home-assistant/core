"""Tests for the IPP config flow."""
import aiohttp
from asynctest import patch
from pyipp import IPPConnectionUpgradeRequired
from pyipp.models import Printer

from homeassistant.components.ipp.const import CONF_BASE_PATH, CONF_UUID, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    MOCK_USER_INPUT,
    MOCK_ZEROCONF_IPP_SERVICE_INFO,
    MOCK_ZEROCONF_IPPS_SERVICE_INFO,
    init_integration,
    load_fixture_binary,
)

from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_PRINTER = Printer.from_dict({"printer-make-and-model": "EPSON XP-6000 Series"})


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM


async def test_show_zeroconf_form(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the zeroconf confirmation form is served."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    discovery_info = {**MOCK_ZEROCONF_IPP_SERVICE_INFO}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["description_placeholders"] == {CONF_NAME: "EPSON XP-6000 Series"}


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on IPP connection error."""
    aioclient_mock.post("http://192.168.1.31:631/ipp/print", exc=aiohttp.ClientError)

    user_input = {**MOCK_USER_INPUT}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input,
    )

    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "connection_error"}


async def test_zeroconf_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on IPP connection error."""
    aioclient_mock.post("http://192.168.1.31:631/ipp/print", exc=aiohttp.ClientError)

    discovery_info = {**MOCK_ZEROCONF_IPP_SERVICE_INFO}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "connection_error"


async def test_zeroconf_confirm_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on IPP connection error."""
    aioclient_mock.post("http://192.168.1.31:631/ipp/print", exc=aiohttp.ClientError)

    discovery_info = {**MOCK_ZEROCONF_IPP_SERVICE_INFO}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "connection_error"


async def test_user_connection_upgrade_required(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show the user form if connection upgrade required by server."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print", exc=IPPConnectionUpgradeRequired
    )

    user_input = {**MOCK_USER_INPUT}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input,
    )

    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "connection_upgrade"}


async def test_zeroconf_connection_upgrade_required(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on IPP connection error."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print", exc=IPPConnectionUpgradeRequired
    )

    discovery_info = {**MOCK_ZEROCONF_IPP_SERVICE_INFO}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "connection_upgrade"


async def test_user_parse_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort user flow on IPP parse error."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print",
        content="BAD",
        headers={"Content-Type": "application/ipp"},
    )

    user_input = {**MOCK_USER_INPUT}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "parse_error"


async def test_zeroconf_parse_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on IPP parse error."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print",
        content="BAD",
        headers={"Content-Type": "application/ipp"},
    )

    discovery_info = {**MOCK_ZEROCONF_IPP_SERVICE_INFO}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "parse_error"


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort user flow if printer already configured."""
    await init_integration(hass, aioclient_mock)

    user_input = {**MOCK_USER_INPUT}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if printer already configured."""
    await init_integration(hass, aioclient_mock)

    discovery_info = {**MOCK_ZEROCONF_IPP_SERVICE_INFO}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_with_uuid_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if printer already configured."""
    await init_integration(hass, aioclient_mock)

    discovery_info = {
        **MOCK_ZEROCONF_IPP_SERVICE_INFO,
        "properties": {
            **MOCK_ZEROCONF_IPP_SERVICE_INFO["properties"],
            "UUID": "cfe92100-67c4-11d4-a45f-f8d027761251",
        },
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "192.168.1.31"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_full_user_no_uuid_flow_implementation(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test the full manual user flow from start to finish with no uuid."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.ipp.config_flow.IPP.printer",
        return_value=MOCK_PRINTER,
    ) as printer_mock:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
        )

    assert len(printer_mock.mock_calls) == 2

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "192.168.1.31"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_UUID] is None

    assert result["result"]
    assert result["result"].unique_id == "url-e8bbb7dc91b23497a763a39c7e5cdb30"


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full zeroconf discovery flow from start to finish."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    discovery_info = {**MOCK_ZEROCONF_IPP_SERVICE_INFO}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_NAME] == "EPSON XP-6000 Series"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"
    assert not result["data"][CONF_SSL]

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_full_zeroconf_tls_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full zeroconf discovery flow from start to finish."""
    aioclient_mock.post(
        "https://192.168.1.31:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    discovery_info = {**MOCK_ZEROCONF_IPPS_SERVICE_INFO}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["description_placeholders"] == {CONF_NAME: "EPSON XP-6000 Series"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_NAME] == "EPSON XP-6000 Series"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"
    assert result["data"][CONF_SSL]

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_full_zeroconf_no_uuid_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full zeroconf discovery flow from start to finish."""
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print",
        content=load_fixture_binary("ipp/get-printer-attributes.bin"),
        headers={"Content-Type": "application/ipp"},
    )

    discovery_info = {**MOCK_ZEROCONF_IPP_SERVICE_INFO}
    print(discovery_info)
    with patch(
        "homeassistant.components.ipp.config_flow.IPP.printer",
        return_value=MOCK_PRINTER,
    ) as printer_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info,
        )

    assert len(printer_mock.mock_calls) == 1

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["description_placeholders"] == {CONF_NAME: "EPSON XP-6000 Series"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_NAME] == "EPSON XP-6000 Series"
    assert result["data"][CONF_UUID] is None

    assert result["result"]
    assert result["result"].unique_id == "url-44dca3f61842386da30f39ce86e0dae2"
