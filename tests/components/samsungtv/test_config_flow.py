"""Tests for Samsung TV config flow."""
from unittest.mock import call, patch

from asynctest import mock
import pytest
from samsungctl.exceptions import AccessDenied, UnhandledResponse
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
from homeassistant.const import CONF_HOST, CONF_ID, CONF_METHOD, CONF_NAME

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

AUTODETECT_WEBSOCKET = {
    "name": "HomeAssistant",
    "description": "HomeAssistant",
    "id": "ha.component.samsung",
    "method": "websocket",
    "port": None,
    "host": "fake_host",
    "timeout": 1,
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


@pytest.fixture(name="remote")
def remote_fixture():
    """Patch the samsungctl Remote."""
    with patch("samsungctl.Remote") as remote_class, patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ) as socket_class:
        remote = mock.Mock()
        remote.__enter__ = mock.Mock()
        remote.__exit__ = mock.Mock()
        remote_class.return_value = remote
        socket = mock.Mock()
        socket_class.return_value = socket
        yield remote


async def test_user(hass, remote):
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
    assert result["type"] == "create_entry"
    assert result["title"] == "fake_name"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_NAME] == "fake_name"
    assert result["data"][CONF_MANUFACTURER] is None
    assert result["data"][CONF_MODEL] is None
    assert result["data"][CONF_ID] is None


async def test_user_missing_auth(hass):
    """Test starting a flow by user with authentication."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=AccessDenied("Boom"),
    ), patch("homeassistant.components.samsungtv.config_flow.socket"):

        # missing authentication
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "auth_missing"


async def test_user_not_supported(hass):
    """Test starting a flow by user for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=UnhandledResponse("Boom"),
    ), patch("homeassistant.components.samsungtv.config_flow.socket"):

        # device not supported
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_supported"


async def test_user_not_successful(hass):
    """Test starting a flow by user but no connection found."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=OSError("Boom"),
    ), patch("homeassistant.components.samsungtv.config_flow.socket"):

        # device not connectable
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


async def test_ssdp_missing_auth(hass):
    """Test starting a flow from discovery with authentication."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
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


async def test_ssdp_not_supported(hass):
    """Test starting a flow from discovery for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
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


async def test_ssdp_not_supported_2(hass):
    """Test starting a flow from discovery for not supported device."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=WebSocketProtocolException("Boom"),
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


async def test_ssdp_not_successful(hass):
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=OSError("Boom"),
    ), patch("homeassistant.components.samsungtv.config_flow.socket"):

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
    assert result["data"][CONF_MANUFACTURER] is None
    assert result["data"][CONF_MODEL] is None
    assert result["data"][CONF_ID] is None

    # failed as already configured
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"

    # check updated device info
    assert result["data"][CONF_MANUFACTURER] == "fake_manufacturer"
    assert result["data"][CONF_MODEL] == "fake_model"
    assert result["data"][CONF_ID] == "fake_uuid"


async def test_autodetect_websocket(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch("homeassistant.components.samsungtv.config_flow.Remote") as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "websocket"
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_WEBSOCKET)]


async def test_autodetect_auth_missing(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=[AccessDenied("Boom")],
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "auth_missing"
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_WEBSOCKET)]


async def test_autodetect_not_supported(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=[UnhandledResponse("Boom")],
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_supported"
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_WEBSOCKET)]


async def test_autodetect_legacy(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=[OSError("Boom"), mock.DEFAULT],
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_METHOD] == "legacy"
        assert remote.call_count == 2
        assert remote.call_args_list == [
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_LEGACY),
        ]


async def test_autodetect_none(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=OSError("Boom"),
    ) as remote:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "not_successful"
        assert remote.call_count == 2
        assert remote.call_args_list == [
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_LEGACY),
        ]
