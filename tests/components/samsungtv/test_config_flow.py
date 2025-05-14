"""Tests for Samsung TV config flow."""

from copy import deepcopy
from ipaddress import ip_address
import socket
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import pytest
from samsungctl.exceptions import AccessDenied, UnhandledResponse
from samsungtvws.async_remote import SamsungTVWSAsyncRemote
from samsungtvws.exceptions import (
    ConnectionFailure,
    HttpApiError,
    ResponseError,
    UnauthorizedError,
)
from websockets import frames
from websockets.exceptions import ConnectionClosedError, WebSocketException

from homeassistant import config_entries
from homeassistant.components.samsungtv.config_flow import (
    SamsungTVConfigFlow,
    _strip_uuid,
)
from homeassistant.components.samsungtv.const import (
    CONF_MANUFACTURER,
    CONF_SESSION_ID,
    CONF_SSDP_MAIN_TV_AGENT_LOCATION,
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DEFAULT_MANUFACTURER,
    DOMAIN,
    LEGACY_PORT,
    METHOD_LEGACY,
    RESULT_AUTH_MISSING,
    RESULT_CANNOT_CONNECT,
    RESULT_NOT_SUPPORTED,
    TIMEOUT_REQUEST,
    TIMEOUT_WEBSOCKET,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_MODEL,
    CONF_PIN,
    CONF_PORT,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import BaseServiceInfo, FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    SsdpServiceInfo,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component

from .const import (
    ENTRYDATA_ENCRYPTED_WEBSOCKET,
    ENTRYDATA_LEGACY,
    ENTRYDATA_WEBSOCKET,
    MOCK_SSDP_DATA,
    MOCK_SSDP_DATA_MAIN_TV_AGENT_ST,
    MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
)

from tests.common import MockConfigEntry, load_json_object_fixture

RESULT_ALREADY_CONFIGURED = "already_configured"
RESULT_ALREADY_IN_PROGRESS = "already_in_progress"

MOCK_USER_DATA = {CONF_HOST: "fake_host"}

MOCK_DHCP_DATA = DhcpServiceInfo(
    ip="10.10.12.34", macaddress="aabbccddeeff", hostname="fake_hostname"
)
MOCK_ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
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
MOCK_DEVICE_INFO = {
    "device": {
        "type": "Samsung SmartTV",
        "name": "fake_name",
        "modelName": "fake_model",
    },
    "id": "123",
}

AUTODETECT_LEGACY = {
    "name": "HomeAssistant",
    "description": "HomeAssistant",
    "id": "ha.component.samsung",
    "method": METHOD_LEGACY,
    "port": LEGACY_PORT,
    "host": "10.20.43.21",
    "timeout": TIMEOUT_REQUEST,
}
AUTODETECT_WEBSOCKET_SSL = {
    "host": "10.20.43.21",
    "name": "HomeAssistant",
    "port": 8002,
    "timeout": TIMEOUT_REQUEST,
    "token": None,
}
DEVICEINFO_WEBSOCKET_SSL = {
    "host": "10.20.43.21",
    "session": ANY,
    "port": 8002,
    "timeout": TIMEOUT_WEBSOCKET,
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("remote_legacy", "rest_api_failing")
async def test_user_legacy(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    # show form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Wrong host allow to retry
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        side_effect=socket.gaierror("[Error -2] Name or Service not known"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}

    # Good host creates entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_DATA
    )
    # legacy tv entry created
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.20.43.21"
    assert result["data"][CONF_HOST] == "10.20.43.21"
    assert result["data"][CONF_METHOD] == METHOD_LEGACY
    assert result["data"][CONF_MANUFACTURER] == DEFAULT_MANUFACTURER
    assert result["data"][CONF_MODEL] is None
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("rest_api_failing")
async def test_user_legacy_does_not_ok_first_time(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    # show form
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=AccessDenied("Boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        # entry was added
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

    with patch("homeassistant.components.samsungtv.bridge.Remote"):
        # entry was added
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input={}
        )

    # legacy tv entry created
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "10.20.43.21"
    assert result3["data"][CONF_HOST] == "10.20.43.21"
    assert result3["data"][CONF_METHOD] == METHOD_LEGACY
    assert result3["data"][CONF_MANUFACTURER] == DEFAULT_MANUFACTURER
    assert result3["data"][CONF_MODEL] is None
    assert result3["result"].unique_id is None


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_user_websocket(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom")
    ):
        # show form
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # entry was added
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        # websocket tv entry created
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Living Room (82GXARRS)"
        assert result["data"][CONF_HOST] == "10.20.43.21"
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_MANUFACTURER] == "Samsung"
        assert result["data"][CONF_MODEL] == "82GXARRS"
        assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote_encrypted_websocket", "rest_api_non_ssl_only")
async def test_user_encrypted_websocket(
    hass: HomeAssistant,
) -> None:
    """Test starting a flow from ssdp for a supported device populates the mac."""
    # show form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.samsungtv.config_flow.SamsungTVEncryptedWSAsyncAuthenticator",
        autospec=True,
    ) as authenticator_mock:
        authenticator_mock.return_value.try_pin.side_effect = [
            None,
            "037739871315caef138547b03e348b72",
        ]
        authenticator_mock.return_value.get_session_id_and_close.return_value = "1"

        # entry was added
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "encrypted_pairing"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input={CONF_PIN: "invalid"}
        )
        assert result3["step_id"] == "encrypted_pairing"
        assert result3["errors"] == {"base": "invalid_pin"}

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], user_input={CONF_PIN: "1234"}
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "TV-UE48JU6470 (UE48JU6400)"
    assert result4["data"][CONF_HOST] == "10.20.43.21"
    assert result4["data"][CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    assert result4["data"][CONF_MANUFACTURER] == "Samsung"
    assert result4["data"][CONF_MODEL] == "UE48JU6400"
    assert result4["data"][CONF_SSDP_RENDERING_CONTROL_LOCATION] is None
    assert result4["data"][CONF_TOKEN] == "037739871315caef138547b03e348b72"
    assert result4["data"][CONF_SESSION_ID] == "1"
    assert result4["result"].unique_id == "223da676-497a-4e06-9507-5e27ec4f0fb3"


@pytest.mark.usefixtures("rest_api_failing")
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
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pairing"
        assert result["errors"] == {"base": "auth_missing"}

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError,
    ):
        # legacy device fails to connect after auth failed
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("rest_api_failing")
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
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures("rest_api", "remote_encrypted_websocket_failing")
async def test_user_websocket_not_supported(hass: HomeAssistant) -> None:
    """Test starting a flow by user for not supported device."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
            side_effect=WebSocketException("Boom"),
        ),
    ):
        # websocket device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures("rest_api", "remote_encrypted_websocket_failing")
async def test_user_websocket_access_denied(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test starting a flow by user for not supported device."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
            side_effect=ConnectionClosedError(rcvd=None, sent=frames.Close(1002, "")),
        ),
    ):
        # websocket device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_NOT_SUPPORTED
    assert "Please check the Device Connection Manager on your TV" in caplog.text


@pytest.mark.usefixtures("rest_api", "remote_encrypted_websocket_failing")
async def test_user_websocket_auth_retry(hass: HomeAssistant) -> None:
    """Test starting a flow by user for not supported device."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
            side_effect=UnauthorizedError,
        ),
    ):
        # websocket device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"
    assert result["errors"] == {"base": "auth_missing"}
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room (82GXARRS)"
    assert result["data"][CONF_HOST] == "10.20.43.21"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("rest_api_failing")
async def test_user_not_successful(hass: HomeAssistant) -> None:
    """Test starting a flow by user but no connection found."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
            side_effect=OSError("Boom"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("rest_api_failing")
async def test_user_not_successful_2(hass: HomeAssistant) -> None:
    """Test starting a flow by user but no connection found."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
            side_effect=ConnectionFailure("Boom"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("remote_legacy", "rest_api_failing")
async def test_ssdp(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery."""
    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UE55H6400"
    assert result["data"][CONF_HOST] == "10.10.12.34"
    assert result["data"][CONF_MANUFACTURER] == "Samsung Electronics"
    assert result["data"][CONF_MODEL] == "UE55H6400"
    assert result["result"].unique_id == "068e7781-006e-1000-bbbf-84a4668d8423"


@pytest.mark.usefixtures("remote_legacy", "rest_api_failing")
async def test_ssdp_no_manufacturer(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery when the manufacturer data is missing."""
    ssdp_data = deepcopy(MOCK_SSDP_DATA)
    ssdp_data.upnp.pop(ATTR_UPNP_MANUFACTURER)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp_data,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.parametrize(
    "data", [MOCK_SSDP_DATA_MAIN_TV_AGENT_ST, MOCK_SSDP_DATA_RENDERING_CONTROL_ST]
)
@pytest.mark.usefixtures("remote_legacy", "rest_api_failing")
async def test_ssdp_legacy_not_remote_control_receiver_udn(
    hass: HomeAssistant, data: SsdpServiceInfo
) -> None:
    """Test we abort if the st is not usable for legacy discovery since it will have a different UDN."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures("remote_legacy", "rest_api_failing")
async def test_ssdp_noprefix(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery when friendly name doesn't start with [TV]."""
    ssdp_data = deepcopy(MOCK_SSDP_DATA)
    ssdp_data.upnp[ATTR_UPNP_FRIENDLY_NAME] = ssdp_data.upnp[ATTR_UPNP_FRIENDLY_NAME][
        4:
    ]

    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp_data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UE55H6400"
    assert result["data"][CONF_HOST] == "10.10.12.34"
    assert result["data"][CONF_MANUFACTURER] == "Samsung Electronics"
    assert result["data"][CONF_MODEL] == "UE55H6400"
    assert result["result"].unique_id == "068e7781-006e-1000-bbbf-84a4668d8423"


@pytest.mark.usefixtures("remote_websocket", "rest_api_failing")
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
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # missing authentication
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pairing"
        assert result["errors"] == {"base": "auth_missing"}

    with patch("homeassistant.components.samsungtv.bridge.Remote"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UE55H6400"
    assert result["data"][CONF_HOST] == "10.10.12.34"
    assert result["data"][CONF_MANUFACTURER] == "Samsung Electronics"
    assert result["data"][CONF_MODEL] == "UE55H6400"
    assert result["result"].unique_id == "068e7781-006e-1000-bbbf-84a4668d8423"


@pytest.mark.usefixtures("remote_websocket", "rest_api_failing")
async def test_ssdp_legacy_not_supported(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVLegacyBridge.async_try_connect",
        return_value=RESULT_NOT_SUPPORTED,
    ):
        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_ssdp_websocket_success_populates_mac_address_and_ssdp_location(
    hass: HomeAssistant,
) -> None:
    """Test starting a flow from ssdp for a supported device populates the mac."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room (82GXARRS)"
    assert result["data"][CONF_HOST] == "10.10.12.34"
    assert result["data"][CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    assert result["data"][CONF_MANUFACTURER] == "Samsung Electronics"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert (
        result["data"][CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "http://10.10.12.34:7676/smp_15_"
    )
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_ssdp_websocket_success_populates_mac_address_and_main_tv_ssdp_location(
    hass: HomeAssistant,
) -> None:
    """Test starting a flow from ssdp for a supported device populates the mac."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_MAIN_TV_AGENT_ST,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room (82GXARRS)"
    assert result["data"][CONF_HOST] == "10.10.12.34"
    assert result["data"][CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    assert result["data"][CONF_MANUFACTURER] == "Samsung Electronics"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert (
        result["data"][CONF_SSDP_MAIN_TV_AGENT_LOCATION]
        == "http://10.10.12.34:7676/smp_2_"
    )
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote_encrypted_websocket", "rest_api_non_ssl_only")
async def test_ssdp_encrypted_websocket_success_populates_mac_address_and_ssdp_location(
    hass: HomeAssistant,
) -> None:
    """Test starting a flow from ssdp for a supported device populates the mac."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.samsungtv.config_flow.SamsungTVEncryptedWSAsyncAuthenticator",
        autospec=True,
    ) as authenticator_mock:
        authenticator_mock.return_value.try_pin.side_effect = [
            None,
            "037739871315caef138547b03e348b72",
        ]
        authenticator_mock.return_value.get_session_id_and_close.return_value = "1"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result2["step_id"] == "encrypted_pairing"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input={CONF_PIN: "invalid"}
        )
        assert result3["step_id"] == "encrypted_pairing"
        assert result3["errors"] == {"base": "invalid_pin"}

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], user_input={CONF_PIN: "1234"}
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "TV-UE48JU6470 (UE48JU6400)"
    assert result4["data"][CONF_HOST] == "10.10.12.34"
    assert result4["data"][CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    assert result4["data"][CONF_MANUFACTURER] == "Samsung Electronics"
    assert result4["data"][CONF_MODEL] == "UE48JU6400"
    assert (
        result4["data"][CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "http://10.10.12.34:7676/smp_15_"
    )
    assert result4["data"][CONF_TOKEN] == "037739871315caef138547b03e348b72"
    assert result4["data"][CONF_SESSION_ID] == "1"
    assert result4["result"].unique_id == "223da676-497a-4e06-9507-5e27ec4f0fb3"


@pytest.mark.usefixtures("rest_api_non_ssl_only")
async def test_ssdp_encrypted_websocket_not_supported(
    hass: HomeAssistant,
) -> None:
    """Test starting a flow from ssdp for an unsupported device populates the mac."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote.start_listening",
        side_effect=WebSocketException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures("rest_api_failing")
async def test_ssdp_websocket_cannot_connect(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery and we cannot connect."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote.start_listening",
            side_effect=WebSocketException("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote",
        ) as remote_websocket,
        patch.object(remote_websocket, "open", side_effect=WebSocketException("Boom")),
    ):
        # device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("remote_legacy")
async def test_ssdp_wrong_manufacturer(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery."""
    ssdp_data = deepcopy(MOCK_SSDP_DATA)
    ssdp_data.upnp[ATTR_UPNP_MANUFACTURER] = ssdp_data.upnp[ATTR_UPNP_MANUFACTURER][7:]
    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp_data,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures("remote_encrypted_websocket_failing")
async def test_ssdp_not_successful(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery but no device found."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
            return_value=MOCK_DEVICE_INFO,
        ),
    ):
        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # device not found
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("remote_encrypted_websocket_failing")
async def test_ssdp_not_successful_2(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery but no device found."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
            side_effect=ConnectionFailure("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
            return_value=MOCK_DEVICE_INFO,
        ),
    ):
        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # device not found
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("remote_legacy", "remote_encrypted_websocket_failing")
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
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # failed as already in progress
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_ALREADY_IN_PROGRESS


@pytest.mark.usefixtures("remote_websocket", "remote_encrypted_websocket_failing")
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
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        assert entry.data[CONF_MANUFACTURER] == DEFAULT_MANUFACTURER
        assert entry.data[CONF_MODEL] == "fake_model"
        assert entry.unique_id == "123"

        # failed as already configured
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == RESULT_ALREADY_CONFIGURED

        # check updated device info
        assert entry.unique_id == "123"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api_non_ssl_only", "remote_encrypted_websocket_failing"
)
async def test_dhcp_wireless(hass: HomeAssistant) -> None:
    """Test starting a flow from dhcp."""
    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TV-UE48JU6470 (UE48JU6400)"
    assert result["data"][CONF_HOST] == "10.10.12.34"
    assert result["data"][CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["data"][CONF_MODEL] == "UE48JU6400"
    assert result["result"].unique_id == "223da676-497a-4e06-9507-5e27ec4f0fb3"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_dhcp_wired(hass: HomeAssistant, rest_api: Mock) -> None:
    """Test starting a flow from dhcp."""
    # Even though it is named "wifiMac", it matches the mac of the wired connection
    rest_api.rest_device_info.return_value = load_json_object_fixture(
        "device_info_UE43LS003.json", DOMAIN
    )
    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Samsung Frame (43) (UE43LS003)"
    assert result["data"][CONF_HOST] == "10.10.12.34"
    assert result["data"][CONF_MAC] == "aa:ee:tt:hh:ee:rr"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["data"][CONF_MODEL] == "UE43LS003"
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api_non_ssl_only", "remote_encrypted_websocket_failing"
)
@pytest.mark.parametrize(
    ("source1", "data1", "source2", "data2", "is_matching_result"),
    [
        (
            config_entries.SOURCE_DHCP,
            MOCK_DHCP_DATA,
            config_entries.SOURCE_DHCP,
            MOCK_DHCP_DATA,
            True,
        ),
        (
            config_entries.SOURCE_DHCP,
            MOCK_DHCP_DATA,
            config_entries.SOURCE_ZEROCONF,
            MOCK_ZEROCONF_DATA,
            False,
        ),
        (
            config_entries.SOURCE_ZEROCONF,
            MOCK_ZEROCONF_DATA,
            config_entries.SOURCE_DHCP,
            MOCK_DHCP_DATA,
            False,
        ),
        (
            config_entries.SOURCE_ZEROCONF,
            MOCK_ZEROCONF_DATA,
            config_entries.SOURCE_ZEROCONF,
            MOCK_ZEROCONF_DATA,
            True,
        ),
    ],
)
async def test_dhcp_zeroconf_already_in_progress(
    hass: HomeAssistant,
    source1: str,
    data1: BaseServiceInfo,
    source2: str,
    data2: BaseServiceInfo,
    is_matching_result: bool,
) -> None:
    """Test starting a flow from dhcp or zeroconf when already in progress."""
    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source1}, data=data1
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    real_is_matching = SamsungTVConfigFlow.is_matching
    return_values = []

    def is_matching(self, other_flow) -> bool:
        return_values.append(real_is_matching(self, other_flow))
        return return_values[-1]

    with patch.object(
        SamsungTVConfigFlow, "is_matching", wraps=is_matching, autospec=True
    ):
        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source2}, data=data2
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_ALREADY_IN_PROGRESS
    # Ensure the is_matching method returned the expected value
    assert return_values == [is_matching_result]


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test starting a flow from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room (82GXARRS)"
    assert result["data"][CONF_HOST] == "127.0.0.1"
    assert result["data"][CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    assert result["data"][CONF_MANUFACTURER] == "Samsung"
    assert result["data"][CONF_MODEL] == "82GXARRS"
    assert result["result"].unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote_websocket", "remote_encrypted_websocket_failing")
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures(
    "remote_legacy",
    "remote_websocket",
    "remote_encrypted_websocket",
    "rest_api_failing",
)
async def test_zeroconf_no_device_info(hass: HomeAssistant) -> None:
    """Test starting a flow from zeroconf where device_info returns None."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_zeroconf_and_dhcp_same_time(hass: HomeAssistant) -> None:
    """Test starting a flow from zeroconf and dhcp."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


@pytest.mark.usefixtures("remote_encrypted_websocket_failing")
async def test_autodetect_websocket(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote"
        ) as remote_websocket,
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
        ) as rest_api_class,
    ):
        remote = Mock(SamsungTVWSAsyncRemote)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock(return_value=False)
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
        remote_websocket.return_value = remote

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_TOKEN] == "123456789"
        remote_websocket.assert_called_once_with(**AUTODETECT_WEBSOCKET_SSL)
        rest_api_class.assert_called_once_with(**DEVICEINFO_WEBSOCKET_SSL)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("remote_encrypted_websocket_failing")
async def test_websocket_no_mac(hass: HomeAssistant, mac_address: Mock) -> None:
    """Test for send key with autodetection of protocol."""
    mac_address.return_value = "gg:ee:tt:mm:aa:cc"
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote"
        ) as remote_websocket,
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
        ) as rest_api_class,
    ):
        remote = Mock(SamsungTVWSAsyncRemote)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock(return_value=False)
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
        remote_websocket.return_value = remote

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_TOKEN] == "123456789"
        assert result["data"][CONF_MAC] == "gg:ee:tt:mm:aa:cc"
        remote_websocket.assert_called_once_with(**AUTODETECT_WEBSOCKET_SSL)
        rest_api_class.assert_called_once_with(**DEVICEINFO_WEBSOCKET_SSL)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_MAC] == "gg:ee:tt:mm:aa:cc"


@pytest.mark.usefixtures("rest_api_failing")
async def test_autodetect_auth_missing(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=AccessDenied("Boom"),
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pairing"
        assert result["errors"] == {"base": "auth_missing"}

        assert remote.call_count == 2
        assert remote.call_args_list == [
            call(AUTODETECT_LEGACY),
            call(AUTODETECT_LEGACY),
        ]
    with patch("homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == RESULT_CANNOT_CONNECT


@pytest.mark.usefixtures("rest_api_failing")
async def test_autodetect_not_supported(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[UnhandledResponse("Boom")],
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_NOT_SUPPORTED
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_LEGACY)]


@pytest.mark.usefixtures("remote_legacy", "rest_api_failing")
async def test_autodetect_legacy(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_METHOD] == METHOD_LEGACY
    assert result["data"][CONF_MAC] is None
    assert result["data"][CONF_PORT] == LEGACY_PORT


async def test_autodetect_none(hass: HomeAssistant) -> None:
    """Test for send key with autodetection of protocol."""
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote",
            side_effect=OSError("Boom"),
        ) as remote,
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest.rest_device_info",
            side_effect=ResponseError,
        ) as rest_device_info,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_CANNOT_CONNECT
        assert remote.call_count == 1
        assert remote.call_args_list == [
            call(AUTODETECT_LEGACY),
        ]
        assert rest_device_info.call_count == 2


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_old_entry(hass: HomeAssistant) -> None:
    """Test update of old entry sets unique id."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRYDATA_LEGACY)
    entry.add_to_hass(hass)

    config_entries_domain = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries_domain) == 1
    assert entry is config_entries_domain[0]
    assert not entry.unique_id

    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    # failed as already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_ALREADY_CONFIGURED

    config_entries_domain = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries_domain) == 1
    entry2 = config_entries_domain[0]

    # check updated device info
    assert entry2.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_missing_mac_unique_id_added_from_dhcp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac and unique id added."""
    # Introduced in #110599, can be removed in 2026.3
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRYDATA_LEGACY, unique_id=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_incorrectly_formatted_mac_unique_id_added_from_dhcp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test incorrectly formatted mac is updated and unique id added."""
    entry_data = ENTRYDATA_LEGACY.copy()
    entry_data[CONF_MAC] = "aabbccddeeff"
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_missing_mac_unique_id_added_from_zeroconf(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac and unique id added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_LEGACY, "host": "127.0.0.1"},
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:zz:ee:rr:oo"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote_legacy", "rest_api_failing")
async def test_update_missing_model_added_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing model added via ssdp on legacy models."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRYDATA_LEGACY,
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MODEL] == "UE55H6400"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_missing_mac_unique_id_ssdp_location_added_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac, ssdp_location, and unique id added via ssdp."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRYDATA_LEGACY, unique_id=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    # Wrong st
    assert CONF_SSDP_RENDERING_CONTROL_LOCATION not in entry.data
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_legacy",
    "remote_websocket",
    "remote_encrypted_websocket_failing",
    "rest_api_failing",
)
async def test_update_zeroconf_discovery_preserved_unique_id(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf discovery preserves unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_LEGACY, CONF_MAC: "aa:bb:zz:ee:rr:oo"},
        unique_id="original",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_NOT_SUPPORTED
    assert entry.data[CONF_MAC] == "aa:bb:zz:ee:rr:oo"
    assert entry.unique_id == "original"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_missing_mac_unique_id_added_ssdp_location_updated_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac and unique id with outdated ssdp_location with the wrong st added via ssdp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **ENTRYDATA_LEGACY,
            CONF_SSDP_RENDERING_CONTROL_LOCATION: "https://1.2.3.4:555/test",
        },
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    # Wrong ST, ssdp location should not change
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION] == "https://1.2.3.4:555/test"
    )
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_missing_mac_unique_id_added_ssdp_location_rendering_st_updated_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac and unique id with outdated ssdp_location with the correct st added via ssdp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **ENTRYDATA_LEGACY,
            CONF_SSDP_RENDERING_CONTROL_LOCATION: "https://1.2.3.4:555/test",
        },
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    # Correct ST, ssdp location should change
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "http://10.10.12.34:7676/smp_15_"
    )
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_missing_mac_unique_id_added_ssdp_location_main_tv_agent_st_updated_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac and unique id with outdated ssdp_location with the correct st added via ssdp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **ENTRYDATA_LEGACY,
            CONF_SSDP_RENDERING_CONTROL_LOCATION: "https://1.2.3.4:555/test",
            CONF_SSDP_MAIN_TV_AGENT_LOCATION: "https://1.2.3.4:555/test",
        },
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_MAIN_TV_AGENT_ST,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    # Main TV Agent ST, ssdp location should change
    assert (
        entry.data[CONF_SSDP_MAIN_TV_AGENT_LOCATION] == "http://10.10.12.34:7676/smp_2_"
    )
    # Rendering control should not be affected
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION] == "https://1.2.3.4:555/test"
    )
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_ssdp_location_rendering_st_updated_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test with outdated ssdp_location with the correct st added via ssdp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_LEGACY, CONF_MAC: "aa:bb:aa:aa:aa:aa"},
        unique_id="be9554b9-c9fb-41f4-8920-22da015376a4",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    # Correct ST, ssdp location should be added
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "http://10.10.12.34:7676/smp_15_"
    )
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_main_tv_ssdp_location_rendering_st_updated_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test with outdated ssdp_location with the correct st added via ssdp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_LEGACY, CONF_MAC: "aa:bb:aa:aa:aa:aa"},
        unique_id="be9554b9-c9fb-41f4-8920-22da015376a4",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_MAIN_TV_AGENT_ST,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    # Correct ST for MainTV, ssdp location should be added
    assert (
        entry.data[CONF_SSDP_MAIN_TV_AGENT_LOCATION] == "http://10.10.12.34:7676/smp_2_"
    )
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_update_missing_mac_added_unique_id_preserved_from_zeroconf(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac and unique id added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_LEGACY, "host": "127.0.0.1"},
        unique_id="0d1cef00-00dc-1000-9c80-4844f7b172de",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:zz:ee:rr:oo"
    assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remote_legacy")
async def test_update_legacy_missing_mac_from_dhcp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRYDATA_LEGACY,
        unique_id="0d1cef00-00dc-1000-9c80-4844f7b172de",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="10.10.12.34", macaddress="aabbccddeeff", hostname="fake_hostname"
        ),
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remote_legacy")
async def test_update_legacy_missing_mac_from_dhcp_no_unique_id(
    hass: HomeAssistant, rest_api: Mock, mock_setup_entry: AsyncMock
) -> None:
    """Test missing mac added when there is no unique id."""
    rest_api.rest_device_info.side_effect = HttpApiError
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRYDATA_LEGACY,
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.samsungtv.bridge.Remote.__enter__",
            return_value=True,
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote.start_listening",
            side_effect=WebSocketException("Boom"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip="10.10.12.34", macaddress="aabbccddeeff", hostname="fake_hostname"
            ),
        )
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == RESULT_NOT_SUPPORTED
    assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert entry.unique_id is None


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_ssdp_location_unique_id_added_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing ssdp_location, and unique id added via ssdp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_LEGACY, CONF_MAC: "aa:bb:aa:aa:aa:aa"},
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    # Wrong st
    assert CONF_SSDP_RENDERING_CONTROL_LOCATION not in entry.data
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_ssdp_location_unique_id_added_from_ssdp_with_rendering_control_st(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test missing ssdp_location, and unique id added via ssdp with rendering control st."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_LEGACY, CONF_MAC: "aa:bb:aa:aa:aa:aa"},
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    # Correct st
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "http://10.10.12.34:7676/smp_15_"
    )
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote_legacy")
async def test_form_reauth_legacy(hass: HomeAssistant) -> None:
    """Test reauthenticate legacy."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRYDATA_LEGACY)
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_form_reauth_websocket(hass: HomeAssistant) -> None:
    """Test reauthenticate websocket."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRYDATA_WEBSOCKET)
    entry.add_to_hass(hass)
    assert entry.state is ConfigEntryState.NOT_LOADED

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("rest_api")
async def test_form_reauth_websocket_cannot_connect(
    hass: HomeAssistant, remote_websocket: Mock
) -> None:
    """Test reauthenticate websocket when we cannot connect on the first attempt."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRYDATA_WEBSOCKET)
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch.object(remote_websocket, "open", side_effect=ConnectionFailure):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": RESULT_AUTH_MISSING}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"


async def test_form_reauth_websocket_not_supported(hass: HomeAssistant) -> None:
    """Test reauthenticate websocket when the device is not supported."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRYDATA_WEBSOCKET)
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == RESULT_NOT_SUPPORTED


@pytest.mark.usefixtures("remote_encrypted_websocket", "rest_api")
async def test_form_reauth_encrypted(hass: HomeAssistant) -> None:
    """Test reauth flow for encrypted TVs."""
    encrypted_entry_data = deepcopy(ENTRYDATA_ENCRYPTED_WEBSOCKET)
    del encrypted_entry_data[CONF_TOKEN]
    del encrypted_entry_data[CONF_SESSION_ID]

    entry = MockConfigEntry(domain=DOMAIN, data=encrypted_entry_data)
    entry.add_to_hass(hass)
    assert entry.state is ConfigEntryState.NOT_LOADED

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.samsungtv.config_flow.SamsungTVEncryptedWSAsyncAuthenticator",
        autospec=True,
    ) as authenticator_mock:
        authenticator_mock.return_value.try_pin.side_effect = [
            None,
            "037739871315caef138547b03e348b72",
        ]
        authenticator_mock.return_value.get_session_id_and_close.return_value = "1"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {}

        # First time on reauth_confirm_encrypted
        # creates the authenticator, start pairing and requests PIN
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm_encrypted"

        # Invalid PIN
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "invalid"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm_encrypted"

        # Valid PIN
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.state is ConfigEntryState.LOADED

    authenticator_mock.assert_called_once()
    assert authenticator_mock.call_args[0] == ("10.10.12.34",)

    authenticator_mock.return_value.start_pairing.assert_called_once()
    assert authenticator_mock.return_value.try_pin.call_count == 2
    assert authenticator_mock.return_value.try_pin.call_args_list == [
        call("invalid"),
        call("1234"),
    ]
    authenticator_mock.return_value.get_session_id_and_close.assert_called_once()

    assert entry.data[CONF_TOKEN] == "037739871315caef138547b03e348b72"
    assert entry.data[CONF_SESSION_ID] == "1"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_incorrect_udn_matching_upnp_udn_unique_id_added_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test updating the wrong udn from ssdp via upnp udn match."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRYDATA_LEGACY,
        unique_id="068e7781-006e-1000-bbbf-84a4668d8423",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures(
    "remote_websocket", "rest_api", "remote_encrypted_websocket_failing"
)
async def test_update_incorrect_udn_matching_mac_unique_id_added_from_ssdp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test updating the wrong udn from ssdp via mac match."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_LEGACY, CONF_MAC: "aa:bb:aa:aa:aa:aa"},
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote_websocket")
async def test_update_incorrect_udn_matching_mac_from_dhcp(
    hass: HomeAssistant, rest_api: Mock, mock_setup_entry: AsyncMock
) -> None:
    """Test that DHCP updates the wrong udn from ssdp via mac match."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_WEBSOCKET, CONF_MAC: "aa:bb:aa:aa:aa:aa"},
        source=config_entries.SOURCE_SSDP,
        unique_id="0d1cef00-00dc-1000-9c80-4844f7b172de",
    )
    entry.add_to_hass(hass)

    assert entry.data[CONF_HOST] == MOCK_DHCP_DATA.ip
    assert entry.data[CONF_MAC] == dr.format_mac(
        rest_api.rest_device_info.return_value["device"]["wifiMac"]
    )
    assert entry.unique_id != _strip_uuid(rest_api.rest_device_info.return_value["id"])

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Same IP + same MAC => unique id updated
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4"


@pytest.mark.usefixtures("remote_websocket")
async def test_no_update_incorrect_udn_not_matching_mac_from_dhcp(
    hass: HomeAssistant, rest_api: Mock, mock_setup_entry: AsyncMock
) -> None:
    """Test that DHCP does not update the wrong udn from ssdp via host match."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRYDATA_WEBSOCKET, CONF_MAC: "aa:bb:ss:ss:dd:pp"},
        source=config_entries.SOURCE_SSDP,
        unique_id="0d1cef00-00dc-1000-9c80-4844f7b172de",
    )
    entry.add_to_hass(hass)

    assert entry.data[CONF_HOST] == MOCK_DHCP_DATA.ip
    assert entry.data[CONF_MAC] != dr.format_mac(
        rest_api.rest_device_info.return_value["device"]["wifiMac"]
    )
    assert entry.unique_id != _strip_uuid(rest_api.rest_device_info.return_value["id"])

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=MOCK_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 0

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Same IP + different MAC => unique id not updated
    assert entry.unique_id == "0d1cef00-00dc-1000-9c80-4844f7b172de"


@pytest.mark.usefixtures("remote_websocket", "remote_encrypted_websocket_failing")
async def test_ssdp_update_mac(hass: HomeAssistant) -> None:
    """Ensure that MAC address is correctly updated from SSDP."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=MOCK_DEVICE_INFO,
    ):
        # entry was added
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        assert entry.data[CONF_MANUFACTURER] == DEFAULT_MANUFACTURER
        assert entry.data[CONF_MODEL] == "fake_model"
        assert entry.data[CONF_MAC] is None
        assert entry.unique_id == "123"

    device_info = deepcopy(MOCK_DEVICE_INFO)
    device_info["device"]["wifiMac"] = "none"
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=device_info,
    ):
        # Updated
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_ALREADY_CONFIGURED

        # ensure mac wasn't updated with "none"
        assert entry.data[CONF_MAC] is None
        assert entry.unique_id == "123"

    device_info = deepcopy(MOCK_DEVICE_INFO)
    device_info["device"]["wifiMac"] = "aa:bb:cc:dd:ee:ff"
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=device_info,
    ):
        # Updated
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == RESULT_ALREADY_CONFIGURED

        # ensure mac was updated with new wifiMac value
        assert entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"
        assert entry.unique_id == "123"
