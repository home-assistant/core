"""Tests for Samsung TV config flow."""
import socket
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import pytest
from samsungctl.exceptions import AccessDenied, UnhandledResponse
from samsungtvws.async_remote import SamsungTVWSAsyncRemote
from samsungtvws.exceptions import ConnectionFailure, HttpApiError
from websockets.exceptions import WebSocketException, WebSocketProtocolError

from homeassistant import config_entries
from homeassistant.components import dhcp, ssdp, zeroconf
from homeassistant.components.samsungtv.const import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    DEFAULT_MANUFACTURER,
    DOMAIN,
    LEGACY_PORT,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    RESULT_AUTH_MISSING,
    RESULT_CANNOT_CONNECT,
    RESULT_NOT_SUPPORTED,
    RESULT_UNKNOWN_HOST,
    TIMEOUT_REQUEST,
    TIMEOUT_WEBSOCKET,
)
from homeassistant.components.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import SAMPLE_APP_LIST

from tests.common import MockConfigEntry

RESULT_ALREADY_CONFIGURED = "already_configured"
RESULT_ALREADY_IN_PROGRESS = "already_in_progress"

MOCK_IMPORT_DATA = {
    CONF_HOST: "fake_host",
    CONF_NAME: "fake",
    CONF_PORT: 55000,
}
MOCK_IMPORT_DATA_WITHOUT_NAME = {
    CONF_HOST: "fake_host",
}
MOCK_IMPORT_WSDATA = {
    CONF_HOST: "fake_host",
    CONF_NAME: "fake",
    CONF_PORT: 8002,
}
MOCK_USER_DATA = {CONF_HOST: "fake_host", CONF_NAME: "fake_name"}
MOCK_SSDP_DATA = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location="https://fake_host:12345/test",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "[TV] fake_name",
        ATTR_UPNP_MANUFACTURER: "Samsung fake_manufacturer",
        ATTR_UPNP_MODEL_NAME: "fake_model",
        ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172de",
    },
)
MOCK_SSDP_DATA_NOPREFIX = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location="http://fake2_host:12345/test",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "fake2_name",
        ATTR_UPNP_MANUFACTURER: "Samsung fake2_manufacturer",
        ATTR_UPNP_MODEL_NAME: "fake2_model",
        ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172df",
    },
)
MOCK_SSDP_DATA_WRONGMODEL = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location="http://fake2_host:12345/test",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "fake2_name",
        ATTR_UPNP_MANUFACTURER: "fake2_manufacturer",
        ATTR_UPNP_MODEL_NAME: "HW-Qfake",
        ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172df",
    },
)
MOCK_DHCP_DATA = dhcp.DhcpServiceInfo(
    ip="fake_host", macaddress="aa:bb:dd:hh:cc:pp", hostname="fake_hostname"
)
EXISTING_IP = "192.168.40.221"
MOCK_ZEROCONF_DATA = zeroconf.ZeroconfServiceInfo(
    host="fake_host",
    addresses=["fake_host"],
    hostname="mock_hostname",
    name="mock_name",
    port=1234,
    properties={
        "deviceid": "aa:bb:zz:ee:rr:oo",
        "manufacturer": "fake_manufacturer",
        "model": "fake_model",
        "serialNumber": "fake_serial",
    },
    type="mock_type",
)
MOCK_OLD_ENTRY = {
    CONF_HOST: "fake_host",
    CONF_ID: "0d1cef00-00dc-1000-9c80-4844f7b172de_old",
    CONF_IP_ADDRESS: EXISTING_IP,
    CONF_METHOD: "legacy",
    CONF_PORT: None,
}
MOCK_LEGACY_ENTRY = {
    CONF_HOST: EXISTING_IP,
    CONF_ID: "0d1cef00-00dc-1000-9c80-4844f7b172de_old",
    CONF_METHOD: "legacy",
    CONF_PORT: None,
}
MOCK_WS_ENTRY = {
    CONF_HOST: "fake_host",
    CONF_METHOD: METHOD_WEBSOCKET,
    CONF_PORT: 8002,
    CONF_MODEL: "any",
    CONF_NAME: "any",
}
MOCK_DEVICE_INFO = {
    "device": {
        "type": "Samsung SmartTV",
        "name": "fake_name",
        "modelName": "fake_model",
    },
    "id": "123",
}
MOCK_DEVICE_INFO_2 = {
    "device": {
        "type": "Samsung SmartTV",
        "name": "fake2_name",
        "modelName": "fake2_model",
    },
    "id": "345",
}

AUTODETECT_LEGACY = {
    "name": "HomeAssistant",
    "description": "HomeAssistant",
    "id": "ha.component.samsung",
    "method": "legacy",
    "port": None,
    "host": "fake_host",
    "timeout": TIMEOUT_REQUEST,
}
AUTODETECT_WEBSOCKET_PLAIN = {
    "host": "fake_host",
    "name": "HomeAssistant",
    "port": 8001,
    "timeout": TIMEOUT_REQUEST,
    "token": None,
}
AUTODETECT_WEBSOCKET_SSL = {
    "host": "fake_host",
    "name": "HomeAssistant",
    "port": 8002,
    "timeout": TIMEOUT_REQUEST,
    "token": None,
}
DEVICEINFO_WEBSOCKET_SSL = {
    "host": "fake_host",
    "session": ANY,
    "port": 8002,
    "timeout": TIMEOUT_WEBSOCKET,
}


@pytest.mark.usefixtures("remote")
async def test_user_legacy(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    # show form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_DATA
    )
    # legacy tv entry created
    assert result["type"] == "create_entry"
    assert result["title"] == "fake_name"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "fake_name"
    assert result["data"][CONF_METHOD] == "legacy"
    assert result["data"][CONF_MANUFACTURER] == DEFAULT_MANUFACTURER
    assert result["data"][CONF_MODEL] is None
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("remotews")
async def test_user_websocket(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom")
    ):
        # show form
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        # entry was added
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        # websocket tv entry created
        assert result["type"] == "create_entry"
        assert result["title"] == "Living Room (82GXARRS)"
        assert result["data"][CONF_HOST] == "fake_host"
        assert result["data"][CONF_NAME] == "Living Room"
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_MANUFACTURER] == "Samsung"
        assert result["data"][CONF_MODEL] == "82GXARRS"
        assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remotews")
async def test_user_legacy_missing_auth(hass: HomeAssistant) -> None:
    """Test starting a flow by user with authentication."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=AccessDenied("Boom"),
    ):
        # legacy device missing authentication
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_AUTH_MISSING


async def test_user_legacy_not_supported(hass: HomeAssistant) -> None:
    """Test starting a flow by user for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=UnhandledResponse("Boom"),
    ):
        # legacy device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED


async def test_user_websocket_not_supported(hass: HomeAssistant) -> None:
    """Test starting a flow by user for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
        side_effect=WebSocketProtocolError("Boom"),
    ):
        # websocket device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED


async def test_user_not_successful(hass: HomeAssistant) -> None:
    """Test starting a flow by user but no connection found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
        side_effect=OSError("Boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_CANNOT_CONNECT


async def test_user_not_successful_2(hass: HomeAssistant) -> None:
    """Test starting a flow by user but no connection found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
        side_effect=ConnectionFailure("Boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("remote")
async def test_ssdp(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=MOCK_DEVICE_INFO,
    ):
        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # entry was added
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "fake_name (fake_model)"
        assert result["data"][CONF_HOST] == "fake_host"
        assert result["data"][CONF_NAME] == "fake_name"
        assert result["data"][CONF_MANUFACTURER] == "Samsung fake_manufacturer"
        assert result["data"][CONF_MODEL] == "fake_model"
        assert result["result"].unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remote")
async def test_ssdp_noprefix(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery without prefixes."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=MOCK_DEVICE_INFO_2,
    ):
        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=MOCK_SSDP_DATA_NOPREFIX,
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        with patch(
            "homeassistant.components.samsungtv.bridge.Remote.__enter__",
            return_value=True,
        ):

            # entry was added
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input="whatever"
            )
            assert result["type"] == "create_entry"
            assert result["title"] == "fake2_name (fake2_model)"
            assert result["data"][CONF_HOST] == "fake2_host"
            assert result["data"][CONF_NAME] == "fake2_name"
            assert result["data"][CONF_MANUFACTURER] == "Samsung fake2_manufacturer"
            assert result["data"][CONF_MODEL] == "fake2_model"
            assert result["result"].unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172df"


@pytest.mark.usefixtures("remotews")
async def test_ssdp_legacy_missing_auth(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery with authentication."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=AccessDenied("Boom"),
    ):

        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # missing authentication

        with patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVLegacyBridge.async_try_connect",
            return_value=RESULT_AUTH_MISSING,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input="whatever"
            )
            assert result["type"] == "abort"
            assert result["reason"] == RESULT_AUTH_MISSING


@pytest.mark.usefixtures("remote", "remotews")
async def test_ssdp_legacy_not_supported(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery for not supported device."""

    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVLegacyBridge.async_try_connect",
        return_value=RESULT_NOT_SUPPORTED,
    ):
        # device not supported
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures("remote", "remotews")
async def test_ssdp_websocket_success_populates_mac_address(
    hass: HomeAssistant,
) -> None:
    """Test starting a flow from ssdp for a supported device populates the mac."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Living Room (82GXARRS)"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "Living Room"
    assert result["data"][CONF_MAC] == "aa:bb:ww:ii:ff:ii"
    assert result["data"][CONF_MANUFACTURER] == "Samsung fake_manufacturer"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert result["result"].unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


async def test_ssdp_websocket_not_supported(
    hass: HomeAssistant, rest_api: Mock
) -> None:
    """Test starting a flow from discovery for not supported device."""
    rest_api.rest_device_info.return_value = None
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote",
    ) as remotews, patch.object(
        remotews, "open", side_effect=WebSocketProtocolError("Boom")
    ):
        # device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures("remote")
async def test_ssdp_model_not_supported(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery."""

    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_WRONGMODEL,
    )
    assert result["type"] == "abort"
    assert result["reason"] == RESULT_NOT_SUPPORTED


async def test_ssdp_not_successful(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=MOCK_DEVICE_INFO,
    ):

        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # device not found
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_CANNOT_CONNECT


async def test_ssdp_not_successful_2(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
        side_effect=ConnectionFailure("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=MOCK_DEVICE_INFO,
    ):

        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # device not found
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("remote")
async def test_ssdp_already_in_progress(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery twice."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=MOCK_DEVICE_INFO,
    ):

        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # failed as already in progress
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_ALREADY_IN_PROGRESS


@pytest.mark.usefixtures("remote")
async def test_ssdp_already_configured(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery when already configured."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=MOCK_DEVICE_INFO,
    ):

        # entry was added
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        entry = result["result"]
        assert entry.data[CONF_MANUFACTURER] == DEFAULT_MANUFACTURER
        assert entry.data[CONF_MODEL] is None
        assert entry.unique_id is None

        # failed as already configured
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result2["type"] == "abort"
        assert result2["reason"] == RESULT_ALREADY_CONFIGURED

        # check updated device info
        assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remote")
async def test_import_legacy(hass: HomeAssistant) -> None:
    """Test importing from yaml with hostname."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_IMPORT_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["title"] == "fake"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "fake"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["result"].unique_id is None

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_METHOD] == METHOD_LEGACY
    assert entries[0].data[CONF_PORT] == LEGACY_PORT


@pytest.mark.usefixtures("remote", "remotews")
async def test_import_legacy_without_name(hass: HomeAssistant, rest_api: Mock) -> None:
    """Test importing from yaml without a name."""
    rest_api.rest_device_info.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_IMPORT_DATA_WITHOUT_NAME,
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["title"] == "fake_host"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["result"].unique_id is None

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_METHOD] == METHOD_LEGACY
    assert entries[0].data[CONF_PORT] == LEGACY_PORT


@pytest.mark.usefixtures("remotews")
async def test_import_websocket(hass: HomeAssistant):
    """Test importing from yaml with hostname."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_IMPORT_WSDATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["title"] == "fake"
    assert result["data"][CONF_METHOD] == METHOD_WEBSOCKET
    assert result["data"][CONF_PORT] == 8002
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "fake"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("remotews")
async def test_import_websocket_without_port(hass: HomeAssistant):
    """Test importing from yaml with hostname by no port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_IMPORT_WSDATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["title"] == "fake"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "fake"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["result"].unique_id is None

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_METHOD] == METHOD_WEBSOCKET
    assert entries[0].data[CONF_PORT] == 8002


@pytest.mark.usefixtures("remotews")
async def test_import_unknown_host(hass: HomeAssistant):
    """Test importing from yaml with hostname that does not resolve."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        side_effect=socket.gaierror,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_IMPORT_DATA,
        )
    await hass.async_block_till_done()
    assert result["type"] == "abort"
    assert result["reason"] == RESULT_UNKNOWN_HOST


@pytest.mark.usefixtures("remote", "remotews")
async def test_dhcp(hass: HomeAssistant) -> None:
    """Test starting a flow from dhcp."""
    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Living Room (82GXARRS)"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "Living Room"
    assert result["data"][CONF_MAC] == "aa:bb:ww:ii:ff:ii"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote", "remotews")
async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test starting a flow from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Living Room (82GXARRS)"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "Living Room"
    assert result["data"][CONF_MAC] == "aa:bb:ww:ii:ff:ii"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remotews")
async def test_zeroconf_ignores_soundbar(hass: HomeAssistant, rest_api: Mock) -> None:
    """Test starting a flow from zeroconf where the device is actually a soundbar."""
    rest_api.rest_device_info.return_value = {
        "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
        "device": {
            "modelName": "82GXARRS",
            "wifiMac": "aa:bb:cc:dd:ee:ff",
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "[TV] Living Room",
            "type": "Samsung SoundBar",
        },
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"


@pytest.mark.usefixtures("remote", "remotews")
async def test_zeroconf_no_device_info(hass: HomeAssistant, rest_api: Mock) -> None:
    """Test starting a flow from zeroconf where device_info returns None."""
    rest_api.rest_device_info.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"


@pytest.mark.usefixtures("remotews")
async def test_zeroconf_and_dhcp_same_time(hass: HomeAssistant) -> None:
    """Test starting a flow from zeroconf and dhcp."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_in_progress"


async def test_autodetect_websocket(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote"
    ) as remotews, patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
    ) as rest_api_class:
        remote = Mock(SamsungTVWSAsyncRemote)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock(return_value=False)
        remote.app_list.return_value = SAMPLE_APP_LIST
        rest_api_class.return_value.rest_device_info = AsyncMock(
            return_value={
                "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
                "device": {
                    "modelName": "82GXARRS",
                    "networkType": "wireless",
                    "wifiMac": "aa:bb:cc:dd:ee:ff",
                    "udn": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "name": "[TV] Living Room",
                    "type": "Samsung SmartTV",
                },
            }
        )
        remote.token = "123456789"
        remotews.return_value = remote

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_TOKEN] == "123456789"
        remotews.assert_called_once_with(**AUTODETECT_WEBSOCKET_SSL)
        rest_api_class.assert_called_once_with(**DEVICEINFO_WEBSOCKET_SSL)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"


async def test_websocket_no_mac(hass: HomeAssistant, mac_address: Mock) -> None:
    """Test for send key with autodetection of protocol."""
    mac_address.return_value = "gg:ee:tt:mm:aa:cc"
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote"
    ) as remotews, patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
    ) as rest_api_class:
        remote = Mock(SamsungTVWSAsyncRemote)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock(return_value=False)
        remote.app_list.return_value = SAMPLE_APP_LIST
        rest_api_class.return_value.rest_device_info = AsyncMock(
            return_value={
                "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
                "device": {
                    "modelName": "82GXARRS",
                    "networkType": "lan",
                    "udn": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
                    "name": "[TV] Living Room",
                    "type": "Samsung SmartTV",
                },
            }
        )

        remote.token = "123456789"
        remotews.return_value = remote

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_TOKEN] == "123456789"
        assert result["data"][CONF_MAC] == "gg:ee:tt:mm:aa:cc"
        remotews.assert_called_once_with(**AUTODETECT_WEBSOCKET_SSL)
        rest_api_class.assert_called_once_with(**DEVICEINFO_WEBSOCKET_SSL)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_MAC] == "gg:ee:tt:mm:aa:cc"


async def test_autodetect_auth_missing(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[AccessDenied("Boom")],
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_AUTH_MISSING
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_LEGACY)]


async def test_autodetect_not_supported(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[UnhandledResponse("Boom")],
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_LEGACY)]


@pytest.mark.usefixtures("remote")
async def test_autodetect_legacy(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_METHOD] == "legacy"
    assert result["data"][CONF_NAME] == "fake_name"
    assert result["data"][CONF_MAC] is None
    assert result["data"][CONF_PORT] == LEGACY_PORT


async def test_autodetect_none(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    mock_remotews = Mock()
    mock_remotews.__aenter__ = AsyncMock(return_value=mock_remotews)
    mock_remotews.__aexit__ = AsyncMock()
    mock_remotews.open = Mock(side_effect=OSError("Boom"))

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ) as remote, patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote",
        return_value=mock_remotews,
    ) as remotews:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_CANNOT_CONNECT
        assert remote.call_count == 1
        assert remote.call_args_list == [
            call(AUTODETECT_LEGACY),
        ]
        assert remotews.call_count == 2
        assert remotews.call_args_list == [
            call(**AUTODETECT_WEBSOCKET_SSL),
            call(**AUTODETECT_WEBSOCKET_PLAIN),
        ]


@pytest.mark.usefixtures("remotews")
async def test_update_old_entry(hass: HomeAssistant) -> None:
    """Test update of old entry."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        remote().rest_device_info.return_value = {
            "device": {
                "modelName": "fake_model2",
                "name": "[TV] Fake Name",
                "udn": "uuid:fake_serial",
            }
        }

        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_OLD_ENTRY)
        entry.add_to_hass(hass)

        config_entries_domain = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries_domain) == 1
        assert entry is config_entries_domain[0]
        assert entry.data[CONF_ID] == "0d1cef00-00dc-1000-9c80-4844f7b172de_old"
        assert entry.data[CONF_IP_ADDRESS] == EXISTING_IP
        assert not entry.unique_id

        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()

        # failed as already configured
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_ALREADY_CONFIGURED

        config_entries_domain = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries_domain) == 1
        entry2 = config_entries_domain[0]

        # check updated device info
        assert entry2.data.get(CONF_ID) is not None
        assert entry2.data.get(CONF_IP_ADDRESS) is not None
        assert entry2.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remotews")
async def test_update_missing_mac_unique_id_added_from_dhcp(
    hass: HomeAssistant,
) -> None:
    """Test missing mac and unique id added."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_OLD_ENTRY, unique_id=None)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.samsungtv.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.samsungtv.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=MOCK_DHCP_DATA,
        )
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:dd:hh:cc:pp"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remotews")
async def test_update_missing_mac_unique_id_added_from_zeroconf(
    hass: HomeAssistant,
) -> None:
    """Test missing mac and unique id added."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_OLD_ENTRY, unique_id=None)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.samsungtv.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.samsungtv.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DATA,
        )
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:zz:ee:rr:oo"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remotews")
async def test_update_missing_mac_unique_id_added_from_ssdp(
    hass: HomeAssistant,
) -> None:
    """Test missing mac and unique id added via ssdp."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_OLD_ENTRY, unique_id=None)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.samsungtv.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.samsungtv.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=MOCK_SSDP_DATA,
        )
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:ww:ii:ff:ii"
    assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remotews")
async def test_update_missing_mac_added_unique_id_preserved_from_zeroconf(
    hass: HomeAssistant,
) -> None:
    """Test missing mac and unique id added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_OLD_ENTRY,
        unique_id="0d1cef00-00dc-1000-9c80-4844f7b172de",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.samsungtv.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.samsungtv.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DATA,
        )
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:zz:ee:rr:oo"
    assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remote")
async def test_update_legacy_missing_mac_from_dhcp(hass: HomeAssistant) -> None:
    """Test missing mac added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_LEGACY_ENTRY,
        unique_id="0d1cef00-00dc-1000-9c80-4844f7b172de",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.samsungtv.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.samsungtv.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=EXISTING_IP, macaddress="aa:bb:cc:dd:ee:ff", hostname="fake_hostname"
            ),
        )
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remote")
async def test_update_legacy_missing_mac_from_dhcp_no_unique_id(
    hass: HomeAssistant, rest_api: Mock
) -> None:
    """Test missing mac added when there is no unique id."""
    rest_api.rest_device_info.side_effect = HttpApiError
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_LEGACY_ENTRY,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote.__enter__",
        return_value=True,
    ), patch(
        "homeassistant.components.samsungtv.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.samsungtv.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=EXISTING_IP, macaddress="aa:bb:cc:dd:ee:ff", hostname="fake_hostname"
            ),
        )
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id is None


@pytest.mark.usefixtures("remote")
async def test_form_reauth_legacy(hass: HomeAssistant) -> None:
    """Test reauthenticate legacy."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_OLD_ENTRY)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"entry_id": entry.entry_id, "source": config_entries.SOURCE_REAUTH},
        data=entry.data,
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"


@pytest.mark.usefixtures("remotews")
async def test_form_reauth_websocket(hass: HomeAssistant) -> None:
    """Test reauthenticate websocket."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_WS_ENTRY)
    entry.add_to_hass(hass)
    assert entry.state == config_entries.ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"entry_id": entry.entry_id, "source": config_entries.SOURCE_REAUTH},
        data=entry.data,
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"
    assert entry.state == config_entries.ConfigEntryState.LOADED


async def test_form_reauth_websocket_cannot_connect(
    hass: HomeAssistant, remotews: Mock
) -> None:
    """Test reauthenticate websocket when we cannot connect on the first attempt."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_WS_ENTRY)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"entry_id": entry.entry_id, "source": config_entries.SOURCE_REAUTH},
        data=entry.data,
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch.object(remotews, "open", side_effect=ConnectionFailure):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": RESULT_AUTH_MISSING}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result3["type"] == "abort"
    assert result3["reason"] == "reauth_successful"


async def test_form_reauth_websocket_not_supported(hass: HomeAssistant) -> None:
    """Test reauthenticate websocket when the device is not supported."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_WS_ENTRY)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"entry_id": entry.entry_id, "source": config_entries.SOURCE_REAUTH},
        data=entry.data,
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
        side_effect=WebSocketException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "not_supported"
