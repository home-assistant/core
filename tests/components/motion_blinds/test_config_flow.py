"""Test the Motionblinds config flow."""

import socket
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.motion_blinds import const
from homeassistant.components.motion_blinds.config_flow import DEFAULT_GATEWAY_NAME
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_HOST2 = "5.6.7.8"
TEST_HOST_HA = "9.10.11.12"
TEST_HOST_ANY = "any"
TEST_API_KEY = "12ab345c-d67e-8f"
TEST_API_KEY2 = "f8e76dc5-43ba-21"
TEST_MAC = "ab:bb:cc:dd:ee:ff"
TEST_MAC2 = "ff:ee:dd:cc:bb:aa"
DHCP_FORMATTED_MAC = "aabbccddeeff"
TEST_DEVICE_LIST = {TEST_MAC: Mock()}

TEST_DISCOVERY_1 = {
    TEST_HOST: {
        "msgType": "GetDeviceListAck",
        "mac": TEST_MAC,
        "deviceType": "02000002",
        "ProtocolVersion": "0.9",
        "token": "12345A678B9CDEFG",
        "data": [
            {"mac": "abcdefghujkl", "deviceType": "02000002"},
            {"mac": "abcdefghujkl0001", "deviceType": "10000000"},
            {"mac": "abcdefghujkl0002", "deviceType": "10000000"},
        ],
    }
}

TEST_DISCOVERY_2 = {
    TEST_HOST: {
        "msgType": "GetDeviceListAck",
        "mac": TEST_MAC,
        "deviceType": "02000002",
        "ProtocolVersion": "0.9",
        "token": "12345A678B9CDEFG",
        "data": [
            {"mac": "abcdefghujkl", "deviceType": "02000002"},
            {"mac": "abcdefghujkl0001", "deviceType": "10000000"},
        ],
    },
    TEST_HOST2: {
        "msgType": "GetDeviceListAck",
        "mac": TEST_MAC2,
        "deviceType": "02000002",
        "ProtocolVersion": "0.9",
        "token": "12345A678B9CDEFG",
        "data": [
            {"mac": "abcdefghujkl", "deviceType": "02000002"},
            {"mac": "abcdefghujkl0001", "deviceType": "10000000"},
        ],
    },
}

TEST_INTERFACES = [
    {"enabled": True, "default": True, "ipv4": [{"address": TEST_HOST_HA}]}
]


@pytest.fixture(name="motion_blinds_connect", autouse=True)
def motion_blinds_connect_fixture():
    """Mock Motionblinds connection and entry setup."""
    with (
        patch(
            "homeassistant.components.motion_blinds.gateway.MotionGateway.GetDeviceList",
            return_value=True,
        ),
        patch(
            "homeassistant.components.motion_blinds.gateway.MotionGateway.Update",
            return_value=True,
        ),
        patch(
            "homeassistant.components.motion_blinds.gateway.MotionGateway.Check_gateway_multicast",
            return_value=True,
        ),
        patch(
            "homeassistant.components.motion_blinds.gateway.MotionGateway.device_list",
            TEST_DEVICE_LIST,
        ),
        patch(
            "homeassistant.components.motion_blinds.gateway.MotionGateway.mac",
            TEST_MAC,
        ),
        patch(
            "homeassistant.components.motion_blinds.config_flow.MotionDiscovery.discover",
            return_value=TEST_DISCOVERY_1,
        ),
        patch(
            "homeassistant.components.motion_blinds.config_flow.MotionGateway.GetDeviceList",
            return_value=True,
        ),
        patch(
            "homeassistant.components.motion_blinds.config_flow.MotionGateway.available",
            True,
        ),
        patch(
            "homeassistant.components.motion_blinds.gateway.AsyncMotionMulticast.Start_listen",
            return_value=True,
        ),
        patch(
            "homeassistant.components.motion_blinds.gateway.AsyncMotionMulticast.Stop_listen",
            return_value=True,
        ),
        patch(
            "homeassistant.components.motion_blinds.gateway.network.async_get_adapters",
            return_value=TEST_INTERFACES,
        ),
        patch(
            "homeassistant.components.motion_blinds.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


async def test_config_flow_manual_host_success(hass: HomeAssistant) -> None:
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: TEST_API_KEY},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_API_KEY: TEST_API_KEY,
        const.CONF_INTERFACE: TEST_HOST_ANY,
    }


async def test_config_flow_discovery_1_success(hass: HomeAssistant) -> None:
    """Successful flow with 1 gateway discovered."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.gateway.AsyncMotionMulticast.Stop_listen",
        side_effect=socket.gaierror,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_API_KEY: TEST_API_KEY,
        const.CONF_INTERFACE: TEST_HOST_ANY,
    }


async def test_config_flow_discovery_2_success(hass: HomeAssistant) -> None:
    """Successful flow with 2 gateway discovered."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.config_flow.MotionDiscovery.discover",
        return_value=TEST_DISCOVERY_2,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"
    assert result["data_schema"].schema["select_ip"].container == [
        TEST_HOST,
        TEST_HOST2,
    ]
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"select_ip": TEST_HOST2},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway.Check_gateway_multicast",
        side_effect=socket.timeout,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST2,
        CONF_API_KEY: TEST_API_KEY,
        const.CONF_INTERFACE: TEST_HOST_ANY,
    }


async def test_config_flow_connection_error(hass: HomeAssistant) -> None:
    """Failed flow manually initialized by the user with connection timeout."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway.GetDeviceList",
        side_effect=socket.timeout,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "connection_error"


async def test_config_flow_discovery_fail(hass: HomeAssistant) -> None:
    """Failed flow with no gateways discovered."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.config_flow.MotionDiscovery.discover",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "discovery_error"}


async def test_config_flow_invalid_interface(hass: HomeAssistant) -> None:
    """Failed flow manually initialized by the user with invalid interface."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.gateway.AsyncMotionMulticast.Start_listen",
        side_effect=socket.gaierror,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_API_KEY: TEST_API_KEY,
        const.CONF_INTERFACE: TEST_HOST_ANY,
    }


async def test_dhcp_flow(hass: HomeAssistant) -> None:
    """Successful flow from DHCP discovery."""
    dhcp_data = DhcpServiceInfo(
        ip=TEST_HOST,
        hostname="MOTION_abcdef",
        macaddress=DHCP_FORMATTED_MAC,
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.gateway.AsyncMotionMulticast.Start_listen",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_API_KEY: TEST_API_KEY,
        const.CONF_INTERFACE: TEST_HOST_ANY,
    }


async def test_dhcp_flow_abort(hass: HomeAssistant) -> None:
    """Test that DHCP discovery aborts if not Motionblinds."""
    dhcp_data = DhcpServiceInfo(
        ip=TEST_HOST,
        hostname="MOTION_abcdef",
        macaddress=DHCP_FORMATTED_MAC,
    )

    with patch(
        "homeassistant.components.motion_blinds.config_flow.MotionGateway.GetDeviceList",
        side_effect=socket.timeout,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_motionblinds"


async def test_dhcp_flow_abort_invalid_response(hass: HomeAssistant) -> None:
    """Test that DHCP discovery aborts if device responded with invalid data."""
    dhcp_data = DhcpServiceInfo(
        ip=TEST_HOST,
        hostname="MOTION_abcdef",
        macaddress=DHCP_FORMATTED_MAC,
    )

    with patch(
        "homeassistant.components.motion_blinds.config_flow.MotionGateway.available",
        False,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_motionblinds"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_MAC,
        data={
            CONF_HOST: TEST_HOST,
            CONF_API_KEY: TEST_API_KEY,
        },
        title=DEFAULT_GATEWAY_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={const.CONF_WAIT_FOR_PUSH: False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        const.CONF_WAIT_FOR_PUSH: False,
    }


async def test_change_connection_settings(hass: HomeAssistant) -> None:
    """Test changing connection settings by issuing a second user config flow."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_MAC,
        data={
            CONF_HOST: TEST_HOST,
            CONF_API_KEY: TEST_API_KEY,
            const.CONF_INTERFACE: TEST_HOST_HA,
        },
        title=DEFAULT_GATEWAY_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST2},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: TEST_API_KEY2},
    )

    assert result["type"] is FlowResultType.ABORT
    assert config_entry.data[CONF_HOST] == TEST_HOST2
    assert config_entry.data[CONF_API_KEY] == TEST_API_KEY2
    assert config_entry.data[const.CONF_INTERFACE] == TEST_HOST_ANY
