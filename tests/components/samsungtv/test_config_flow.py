"""Tests for Samsung TV config flow."""
from unittest.mock import Mock, PropertyMock, call, patch

from asynctest import mock
import pytest
from samsungctl.exceptions import AccessDenied, UnhandledResponse
from samsungtvws.exceptions import ConnectionFailure
from websocket import WebSocketProtocolException

from homeassistant.components.samsungtv.const import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    DOMAIN,
)
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.const import CONF_HOST, CONF_ID, CONF_METHOD, CONF_NAME, CONF_TOKEN

MOCK_USER_DATA = {CONF_HOST: "fake_host", CONF_NAME: "fake_name"}
MOCK_SSDP_DATA = {
    ATTR_SSDP_LOCATION: "https://fake_host:12345/test",
    ATTR_UPNP_FRIENDLY_NAME: "[TV]fake_name",
    ATTR_UPNP_MANUFACTURER: "fake_manufacturer",
    ATTR_UPNP_MODEL_NAME: "fake_model",
    ATTR_UPNP_UDN: "uuid:fake_uuid",
}
MOCK_SSDP_DATA_NOPREFIX = {
    ATTR_SSDP_LOCATION: "http://fake2_host:12345/test",
    ATTR_UPNP_FRIENDLY_NAME: "fake2_name",
    ATTR_UPNP_MANUFACTURER: "fake2_manufacturer",
    ATTR_UPNP_MODEL_NAME: "fake2_model",
    ATTR_UPNP_UDN: "fake2_uuid",
}

AUTODETECT_LEGACY = {
    "name": "HomeAssistant",
    "description": "HomeAssistant",
    "id": "ha.component.samsung",
    "method": "legacy",
    "port": None,
    "host": "fake_host",
    "timeout": 31,
}
AUTODETECT_WEBSOCKET_PLAIN = {
    "host": "fake_host",
    "name": "HomeAssistant",
    "port": 8001,
    "timeout": 31,
    "token": None,
}
AUTODETECT_WEBSOCKET_SSL = {
    "host": "fake_host",
    "name": "HomeAssistant",
    "port": 8002,
    "timeout": 31,
    "token": None,
}


@pytest.fixture(name="remote")
def remote_fixture():
    """Patch the samsungctl Remote."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ) as socket_class:
        remote = mock.Mock()
        remote.__enter__ = mock.Mock()
        remote.__exit__ = mock.Mock()
        remote_class.return_value = remote
        socket = mock.Mock()
        socket_class.return_value = socket
        socket_class.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        yield remote


@pytest.fixture(name="remotews")
def remotews_fixture():
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews_class, patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ) as socket_class:
        remotews = mock.Mock()
        remotews.__enter__ = mock.Mock()
        remotews.__exit__ = mock.Mock()
        remotews_class.return_value = remotews
        remotews_class().__enter__().token = "FAKE_TOKEN"
        socket = mock.Mock()
        socket_class.return_value = socket
        socket_class.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        yield remotews


async def test_user_legacy(hass, remote):
    """Test starting a flow by user."""
    # show form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
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
    assert result["data"][CONF_MANUFACTURER] is None
    assert result["data"][CONF_MODEL] is None
    assert result["data"][CONF_ID] is None


async def test_user_websocket(hass, remotews):
    """Test starting a flow by user."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom")
    ):
        # show form
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
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
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_MANUFACTURER] is None
        assert result["data"][CONF_MODEL] is None
        assert result["data"][CONF_ID] is None


async def test_user_legacy_missing_auth(hass):
    """Test starting a flow by user with authentication."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=AccessDenied("Boom"),
    ), patch("homeassistant.components.samsungtv.config_flow.socket"):
        # legacy device missing authentication
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "auth_missing"


async def test_user_legacy_not_supported(hass):
    """Test starting a flow by user for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=UnhandledResponse("Boom"),
    ), patch("homeassistant.components.samsungtv.config_flow.socket"):
        # legacy device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_supported"


async def test_user_websocket_not_supported(hass):
    """Test starting a flow by user for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=WebSocketProtocolException("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ):
        # websocket device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_supported"


async def test_user_not_successful(hass):
    """Test starting a flow by user but no connection found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_successful"


async def test_user_not_successful_2(hass):
    """Test starting a flow by user but no connection found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=ConnectionFailure("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_successful"


async def test_user_already_configured(hass, remote):
    """Test starting a flow by user when already configured."""

    # entry was added
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"

    # failed as already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_ssdp(hass, remote):
    """Test starting a flow from discovery."""

    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "fake_model"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "Samsung fake_model"
    assert result["data"][CONF_MANUFACTURER] == "fake_manufacturer"
    assert result["data"][CONF_MODEL] == "fake_model"
    assert result["data"][CONF_ID] == "fake_uuid"


async def test_ssdp_noprefix(hass, remote):
    """Test starting a flow from discovery without prefixes."""

    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA_NOPREFIX
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "fake2_model"
    assert result["data"][CONF_HOST] == "fake2_host"
    assert result["data"][CONF_NAME] == "Samsung fake2_model"
    assert result["data"][CONF_MANUFACTURER] == "fake2_manufacturer"
    assert result["data"][CONF_MODEL] == "fake2_model"
    assert result["data"][CONF_ID] == "fake2_uuid"


async def test_ssdp_legacy_missing_auth(hass):
    """Test starting a flow from discovery with authentication."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=AccessDenied("Boom"),
    ), patch("homeassistant.components.samsungtv.config_flow.socket"):

        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # missing authentication
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == "auth_missing"


async def test_ssdp_legacy_not_supported(hass):
    """Test starting a flow from discovery for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=UnhandledResponse("Boom"),
    ), patch("homeassistant.components.samsungtv.config_flow.socket"):

        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # device not supported
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_supported"


async def test_ssdp_websocket_not_supported(hass):
    """Test starting a flow from discovery for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=WebSocketProtocolException("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ):
        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # device not supported
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_supported"


async def test_ssdp_not_successful(hass):
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ):

        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # device not found
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_successful"


async def test_ssdp_not_successful_2(hass):
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=ConnectionFailure("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ):

        # confirm to add the entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

        # device not found
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input="whatever"
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_successful"


async def test_ssdp_already_in_progress(hass, remote):
    """Test starting a flow from discovery twice."""

    # confirm to add the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # failed as already in progress
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_ssdp_already_configured(hass, remote):
    """Test starting a flow from discovery when already configured."""

    # entry was added
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.data[CONF_MANUFACTURER] is None
    assert entry.data[CONF_MODEL] is None
    assert entry.data[CONF_ID] is None

    # failed as already configured
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"

    # check updated device info
    assert entry.data[CONF_MANUFACTURER] == "fake_manufacturer"
    assert entry.data[CONF_MODEL] == "fake_model"
    assert entry.data[CONF_ID] == "fake_uuid"


async def test_autodetect_websocket(hass, remote, remotews):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ), patch("homeassistant.components.samsungtv.bridge.SamsungTVWS") as remotews:
        enter = Mock()
        type(enter).token = PropertyMock(return_value="123456789")
        remote = Mock()
        remote.__enter__ = Mock(return_value=enter)
        remote.__exit__ = Mock(return_value=False)
        remotews.return_value = remote

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_TOKEN] == "123456789"
        assert remotews.call_count == 1
        assert remotews.call_args_list == [call(**AUTODETECT_WEBSOCKET_PLAIN)]


async def test_autodetect_websocket_ssl(hass, remote, remotews):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=[WebSocketProtocolException("Boom"), mock.DEFAULT],
    ) as remotews:
        enter = Mock()
        type(enter).token = PropertyMock(return_value="123456789")
        remote = Mock()
        remote.__enter__ = Mock(return_value=enter)
        remote.__exit__ = Mock(return_value=False)
        remotews.return_value = remote

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "websocket"
        assert result["data"][CONF_TOKEN] == "123456789"
        assert remotews.call_count == 2
        assert remotews.call_args_list == [
            call(**AUTODETECT_WEBSOCKET_PLAIN),
            call(**AUTODETECT_WEBSOCKET_SSL),
        ]


async def test_autodetect_auth_missing(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[AccessDenied("Boom")],
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "auth_missing"
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_LEGACY)]


async def test_autodetect_not_supported(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[UnhandledResponse("Boom")],
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_supported"
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_LEGACY)]


async def test_autodetect_legacy(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "legacy"
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_LEGACY)]


async def test_autodetect_none(hass, remote, remotews):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError("Boom"),
    ) as remote, patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS",
        side_effect=OSError("Boom"),
    ) as remotews:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_successful"
        assert remote.call_count == 1
        assert remote.call_args_list == [
            call(AUTODETECT_LEGACY),
        ]
        assert remotews.call_count == 2
        assert remotews.call_args_list == [
            call(**AUTODETECT_WEBSOCKET_PLAIN),
            call(**AUTODETECT_WEBSOCKET_SSL),
        ]
