"""Tests for Samsung TV config flow."""
import socket
from unittest.mock import Mock, PropertyMock, call, patch

from samsungctl.exceptions import AccessDenied, UnhandledResponse
from samsungtvws.exceptions import ConnectionFailure, HttpApiError
from websocket import WebSocketException, WebSocketProtocolException

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
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
    ATTR_SSDP_LOCATION,
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

from tests.common import MockConfigEntry
from tests.components.samsungtv.conftest import (
    RESULT_ALREADY_CONFIGURED,
    RESULT_ALREADY_IN_PROGRESS,
)

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
MOCK_SSDP_DATA = {
    ATTR_SSDP_LOCATION: "https://fake_host:12345/test",
    ATTR_UPNP_FRIENDLY_NAME: "[TV] fake_name",
    ATTR_UPNP_MANUFACTURER: "Samsung fake_manufacturer",
    ATTR_UPNP_MODEL_NAME: "fake_model",
    ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172de",
}
MOCK_SSDP_DATA_NOPREFIX = {
    ATTR_SSDP_LOCATION: "http://fake2_host:12345/test",
    ATTR_UPNP_FRIENDLY_NAME: "fake2_name",
    ATTR_UPNP_MANUFACTURER: "Samsung fake2_manufacturer",
    ATTR_UPNP_MODEL_NAME: "fake2_model",
    ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172df",
}
MOCK_SSDP_DATA_WRONGMODEL = {
    ATTR_SSDP_LOCATION: "http://fake2_host:12345/test",
    ATTR_UPNP_FRIENDLY_NAME: "fake2_name",
    ATTR_UPNP_MANUFACTURER: "fake2_manufacturer",
    ATTR_UPNP_MODEL_NAME: "HW-Qfake",
    ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172df",
}
MOCK_DHCP_DATA = dhcp.DhcpServiceInfo(
    ip="fake_host", macaddress="aa:bb:cc:dd:ee:ff", hostname="fake_hostname"
)
EXISTING_IP = "192.168.40.221"
MOCK_ZEROCONF_DATA = zeroconf.ZeroconfServiceInfo(
    host="fake_host",
    hostname="mock_hostname",
    name="mock_name",
    port=1234,
    properties={
        "deviceid": "aa:bb:cc:dd:ee:ff",
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
    "name": "HomeAssistant",
    "port": 8002,
    "timeout": TIMEOUT_WEBSOCKET,
    "token": "123456789",
}


async def test_user_legacy(hass: HomeAssistant, remote: Mock):
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


async def test_user_websocket(hass: HomeAssistant, remotews: Mock):
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


async def test_user_legacy_missing_auth(
    hass: HomeAssistant, remote: Mock, remotews: Mock
):
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


async def test_user_legacy_not_supported(hass: HomeAssistant, remote: Mock):
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


async def test_user_websocket_not_supported(hass: HomeAssistant, remotews: Mock):
    """Test starting a flow by user for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=WebSocketProtocolException("Boom"),
    ):
        # websocket device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED


async def test_user_not_successful(hass: HomeAssistant, remotews: Mock):
    """Test starting a flow by user but no connection found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=OSError("Boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_CANNOT_CONNECT


async def test_user_not_successful_2(hass: HomeAssistant, remotews: Mock):
    """Test starting a flow by user but no connection found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=ConnectionFailure("Boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_CANNOT_CONNECT


async def test_ssdp(hass: HomeAssistant, remote: Mock):
    """Test starting a flow from discovery."""

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.device_info",
        return_value=MOCK_DEVICE_INFO,
    ), patch("getmac.get_mac_address", return_value="aa:bb:cc:dd:ee:ff"):
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


async def test_ssdp_noprefix(hass: HomeAssistant, remote: Mock):
    """Test starting a flow from discovery without prefixes."""

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.device_info",
        return_value=MOCK_DEVICE_INFO_2,
    ), patch("getmac.get_mac_address", return_value="aa:bb:cc:dd:ee:ff"):
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


async def test_ssdp_legacy_missing_auth(
    hass: HomeAssistant, remote: Mock, remotews: Mock
):
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
            "homeassistant.components.samsungtv.bridge.SamsungTVLegacyBridge.try_connect",
            return_value=RESULT_AUTH_MISSING,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input="whatever"
            )
            assert result["type"] == "abort"
            assert result["reason"] == RESULT_AUTH_MISSING


async def test_ssdp_legacy_not_supported(
    hass: HomeAssistant, remote: Mock, remotews: Mock
):
    """Test starting a flow from discovery for not supported device."""

    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVLegacyBridge.try_connect",
        return_value=RESULT_NOT_SUPPORTED,
    ):
        # device not supported
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED


async def test_ssdp_websocket_success_populates_mac_address(
    hass: HomeAssistant,
    remote: Mock,
    remotews: Mock,
):
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
    assert result["data"][CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert result["data"][CONF_MANUFACTURER] == "Samsung fake_manufacturer"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert result["result"].unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


async def test_ssdp_websocket_not_supported(hass: HomeAssistant, remote: Mock):
    """Test starting a flow from discovery for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=WebSocketProtocolException("Boom"),
    ):
        # device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED


async def test_ssdp_model_not_supported(hass: HomeAssistant, remote: Mock):
    """Test starting a flow from discovery."""

    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_WRONGMODEL,
    )
    assert result["type"] == "abort"
    assert result["reason"] == RESULT_NOT_SUPPORTED


async def test_ssdp_not_successful(
    hass: HomeAssistant, remote: Mock, no_mac_address: Mock
):
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.device_info",
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


async def test_ssdp_not_successful_2(
    hass: HomeAssistant, remote: Mock, no_mac_address: Mock
):
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=ConnectionFailure("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.device_info",
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


async def test_ssdp_already_in_progress(hass: HomeAssistant, remote: Mock):
    """Test starting a flow from discovery twice."""

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.device_info",
        return_value=MOCK_DEVICE_INFO,
    ), patch("getmac.get_mac_address", return_value="aa:bb:cc:dd:ee:ff"):

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


async def test_ssdp_already_configured(hass: HomeAssistant, remote: Mock):
    """Test starting a flow from discovery when already configured."""

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.device_info",
        return_value=MOCK_DEVICE_INFO,
    ), patch("getmac.get_mac_address", return_value="aa:bb:cc:dd:ee:ff"):

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


async def test_import_legacy(hass: HomeAssistant, remote: Mock):
    """Test importing from yaml with hostname."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ), patch("getmac.get_mac_address", return_value="aa:bb:cc:dd:ee:ff"):
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


async def test_import_legacy_without_name(
    hass: HomeAssistant,
    remote: Mock,
    remotews_no_device_info: Mock,
    no_mac_address: Mock,
):
    """Test importing from yaml without a name."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
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


async def test_import_websocket(hass: HomeAssistant, remotews: Mock):
    """Test importing from yaml with hostname."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
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


async def test_import_websocket_without_port(hass: HomeAssistant, remotews: Mock):
    """Test importing from yaml with hostname by no port."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
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


async def test_import_unknown_host(hass: HomeAssistant, remotews: Mock):
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


async def test_dhcp(hass: HomeAssistant, remote: Mock, remotews: Mock):
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
    assert result["data"][CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


async def test_zeroconf(hass: HomeAssistant, remote: Mock, remotews: Mock):
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
    assert result["data"][CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


async def test_zeroconf_ignores_soundbar(hass: HomeAssistant, remotews_soundbar: Mock):
    """Test starting a flow from zeroconf where the device is actually a soundbar."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"


async def test_zeroconf_no_device_info(
    hass: HomeAssistant, remote: Mock, remotews_no_device_info: Mock
):
    """Test starting a flow from zeroconf where device_info returns None."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"


async def test_zeroconf_and_dhcp_same_time(hass: HomeAssistant, remotews: Mock):
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


async def test_autodetect_websocket(hass: HomeAssistant, remote: Mock, remotews: Mock):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews:
        enter = Mock()
        type(enter).token = PropertyMock(return_value="123456789")
        remote = Mock()
        remote.__enter__ = Mock(return_value=enter)
        remote.__exit__ = Mock(return_value=False)
        remote.rest_device_info.return_value = {
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
        remotews.return_value = remote

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_TOKEN] == "123456789"
        assert remotews.call_count == 2
        assert remotews.call_args_list == [
            call(**AUTODETECT_WEBSOCKET_SSL),
            call(**DEVICEINFO_WEBSOCKET_SSL),
        ]
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"


async def test_websocket_no_mac(hass: HomeAssistant, remote: Mock, remotews: Mock):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews, patch(
        "getmac.get_mac_address", return_value="gg:hh:ii:ll:mm:nn"
    ):
        enter = Mock()
        type(enter).token = PropertyMock(return_value="123456789")
        remote = Mock()
        remote.__enter__ = Mock(return_value=enter)
        remote.__exit__ = Mock(return_value=False)
        remote.rest_device_info.return_value = {
            "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
            "device": {
                "modelName": "82GXARRS",
                "networkType": "lan",
                "udn": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
                "name": "[TV] Living Room",
                "type": "Samsung SmartTV",
            },
        }
        remotews.return_value = remote

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_TOKEN] == "123456789"
        assert result["data"][CONF_MAC] == "gg:hh:ii:ll:mm:nn"
        assert remotews.call_count == 2
        assert remotews.call_args_list == [
            call(**AUTODETECT_WEBSOCKET_SSL),
            call(**DEVICEINFO_WEBSOCKET_SSL),
        ]
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_MAC] == "gg:hh:ii:ll:mm:nn"


async def test_autodetect_auth_missing(hass: HomeAssistant, remote: Mock):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[AccessDenied("Boom")],
    ) as remote, patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_AUTH_MISSING
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_LEGACY)]


async def test_autodetect_not_supported(hass: HomeAssistant, remote: Mock):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[UnhandledResponse("Boom")],
    ) as remote, patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == RESULT_NOT_SUPPORTED
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_LEGACY)]


async def test_autodetect_legacy(hass: HomeAssistant, remote: Mock):
    """Test for send key with autodetection of protocol."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_METHOD] == "legacy"
    assert result["data"][CONF_NAME] == "fake_name"
    assert result["data"][CONF_MAC] is None
    assert result["data"][CONF_PORT] == LEGACY_PORT


async def test_autodetect_none(hass: HomeAssistant, remote: Mock, remotews: Mock):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError("Boom"),
    ) as remote, patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=OSError("Boom"),
    ) as remotews, patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
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


async def test_update_old_entry(hass: HomeAssistant, remote: Mock, remotews: Mock):
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


async def test_update_missing_mac_unique_id_added_from_dhcp(hass, remotews: Mock):
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
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


async def test_update_missing_mac_unique_id_added_from_zeroconf(hass, remotews: Mock):
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
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


async def test_update_missing_mac_unique_id_added_from_ssdp(hass, remotews: Mock):
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
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


async def test_update_missing_mac_added_unique_id_preserved_from_zeroconf(
    hass, remotews: Mock
):
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
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


async def test_update_legacy_missing_mac_from_dhcp(hass, remote: Mock):
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


async def test_update_legacy_missing_mac_from_dhcp_no_unique_id(hass, remote: Mock):
    """Test missing mac added when there is no unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_LEGACY_ENTRY,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS.rest_device_info",
        side_effect=HttpApiError,
    ), patch(
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


async def test_form_reauth_legacy(hass, remote: Mock):
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


async def test_form_reauth_websocket(hass, remotews: Mock):
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


async def test_form_reauth_websocket_cannot_connect(hass, remotews: Mock):
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

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=ConnectionFailure,
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
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


async def test_form_reauth_websocket_not_supported(hass, remotews: Mock):
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
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=WebSocketException,
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "not_supported"
