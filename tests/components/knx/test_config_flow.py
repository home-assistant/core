"""Test the KNX config flow."""

from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest
from xknx.exceptions.exception import CommunicationError, InvalidSecureConfiguration
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT
from xknx.io.gateway_scanner import GatewayDescriptor
from xknx.knxip.dib import TunnelingSlotStatus
from xknx.secure.keyring import sync_load_keyring
from xknx.telegram import IndividualAddress

from homeassistant import config_entries
from homeassistant.components.knx.config_flow import (
    CONF_KEYRING_FILE,
    CONF_KNX_GATEWAY,
    CONF_KNX_TUNNELING_TYPE,
    DEFAULT_ENTRY_DATA,
    OPTION_MANUAL_TUNNEL,
)
from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_KNXKEY_FILENAME,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_LOCAL_IP,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_ROUTE_BACK,
    CONF_KNX_ROUTING,
    CONF_KNX_ROUTING_BACKBONE_KEY,
    CONF_KNX_ROUTING_SECURE,
    CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_ID,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_STATE_UPDATER,
    CONF_KNX_TELEGRAM_LOG_SIZE,
    CONF_KNX_TUNNEL_ENDPOINT_IA,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    CONF_KNX_TUNNELING_TCP_SECURE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry, get_fixture_path

FIXTURE_KNXKEYS_PASSWORD = "test"
FIXTURE_KEYRING = sync_load_keyring(
    get_fixture_path("fixture.knxkeys", DOMAIN), FIXTURE_KNXKEYS_PASSWORD
)
FIXTURE_UPLOAD_UUID = "0123456789abcdef0123456789abcdef"
GATEWAY_INDIVIDUAL_ADDRESS = IndividualAddress("1.0.0")


@pytest.fixture(name="knx_setup")
def fixture_knx_setup():
    """Mock KNX entry setup."""
    with (
        patch("homeassistant.components.knx.async_setup", return_value=True),
        patch(
            "homeassistant.components.knx.async_setup_entry", return_value=True
        ) as mock_async_setup_entry,
    ):
        yield mock_async_setup_entry


@contextmanager
def patch_file_upload(return_value=FIXTURE_KEYRING, side_effect=None):
    """Patch file upload. Yields the Keyring instance (return_value)."""
    with (
        patch(
            "homeassistant.components.knx.storage.keyring.process_uploaded_file"
        ) as file_upload_mock,
        patch(
            "homeassistant.components.knx.storage.keyring.sync_load_keyring",
            return_value=return_value,
            side_effect=side_effect,
        ),
        patch(
            "pathlib.Path.mkdir",
        ) as mkdir_mock,
        patch(
            "shutil.move",
        ) as shutil_move_mock,
    ):
        file_upload_mock.return_value.__enter__.return_value = Mock()
        yield return_value
        if side_effect:
            mkdir_mock.assert_not_called()
            shutil_move_mock.assert_not_called()
        else:
            mkdir_mock.assert_called_once()
            shutil_move_mock.assert_called_once()


def _gateway_descriptor(
    ip: str,
    port: int,
    supports_tunnelling_tcp: bool = False,
    requires_secure: bool = False,
    slots: bool = True,
) -> GatewayDescriptor:
    """Get mock gw descriptor."""
    descriptor = GatewayDescriptor(
        name="Test",
        individual_address=GATEWAY_INDIVIDUAL_ADDRESS,
        ip_addr=ip,
        port=port,
        local_interface="eth0",
        local_ip="127.0.0.1",
        supports_routing=True,
        supports_tunnelling=True,
        supports_tunnelling_tcp=supports_tunnelling_tcp,
    )
    descriptor.tunnelling_requires_secure = requires_secure
    descriptor.routing_requires_secure = requires_secure
    if supports_tunnelling_tcp and slots:
        descriptor.tunnelling_slots = {
            IndividualAddress("1.0.240"): TunnelingSlotStatus(True, True, True),
            IndividualAddress("1.0.241"): TunnelingSlotStatus(True, True, False),
            IndividualAddress("1.0.242"): TunnelingSlotStatus(True, True, True),
        }
    return descriptor


class GatewayScannerMock:
    """Mock GatewayScanner."""

    def __init__(self, gateways=None) -> None:
        """Initialize GatewayScannerMock."""
        # Key is a HPAI instance in xknx, but not used in HA anyway.
        self.found_gateways = (
            {f"{gateway.ip_addr}:{gateway.port}": gateway for gateway in gateways}
            if gateways
            else {}
        )

    async def async_scan(self):
        """Mock async generator."""
        for gateway in self.found_gateways:
            yield gateway


async def test_user_single_instance(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_routing_setup(
    gateway_scanner_mock, hass: HomeAssistant, knx_setup
) -> None:
    """Test routing setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "routing"
    assert result2["errors"] == {"base": "no_router_discovered"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Routing as 1.1.110"
    assert result3["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
        CONF_KNX_MCAST_PORT: 3675,
        CONF_KNX_LOCAL_IP: None,
        CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
    }
    knx_setup.assert_called_once()


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_routing_setup_advanced(
    gateway_scanner_mock, hass: HomeAssistant, knx_setup
) -> None:
    """Test routing setup with advanced options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
            "show_advanced_options": True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "routing"
    assert result2["errors"] == {"base": "no_router_discovered"}

    # invalid user input
    result_invalid_input = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_MCAST_GRP: "10.1.2.3",  # no valid multicast group
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "not_a_valid_address",
            CONF_KNX_LOCAL_IP: "no_local_ip",
        },
    )
    assert result_invalid_input["type"] is FlowResultType.FORM
    assert result_invalid_input["step_id"] == "routing"
    assert result_invalid_input["errors"] == {
        CONF_KNX_MCAST_GRP: "invalid_ip_address",
        CONF_KNX_INDIVIDUAL_ADDRESS: "invalid_individual_address",
        CONF_KNX_LOCAL_IP: "invalid_ip_address",
        "base": "no_router_discovered",
    }

    # valid user input
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
            CONF_KNX_LOCAL_IP: "192.168.1.112",
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Routing as 1.1.110"
    assert result3["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
        CONF_KNX_MCAST_PORT: 3675,
        CONF_KNX_LOCAL_IP: "192.168.1.112",
        CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
    }
    knx_setup.assert_called_once()


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_routing_secure_manual_setup(
    gateway_scanner_mock, hass: HomeAssistant, knx_setup
) -> None:
    """Test routing secure setup with manual key config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "routing"
    assert result2["errors"] == {"base": "no_router_discovered"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3671,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.123",
            CONF_KNX_ROUTING_SECURE: True,
        },
    )
    assert result3["type"] is FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source_menu_routing"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {"next_step_id": "secure_routing_manual"},
    )
    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == "secure_routing_manual"
    assert not result4["errors"]

    result_invalid_key1 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        {
            CONF_KNX_ROUTING_BACKBONE_KEY: "xxaacc44bbaacc44bbaacc44bbaaccyy",  # invalid hex string
            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
        },
    )
    assert result_invalid_key1["type"] is FlowResultType.FORM
    assert result_invalid_key1["step_id"] == "secure_routing_manual"
    assert result_invalid_key1["errors"] == {"backbone_key": "invalid_backbone_key"}

    result_invalid_key2 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        {
            CONF_KNX_ROUTING_BACKBONE_KEY: "bbaacc44bbaacc44",  # invalid length
            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
        },
    )
    assert result_invalid_key2["type"] is FlowResultType.FORM
    assert result_invalid_key2["step_id"] == "secure_routing_manual"
    assert result_invalid_key2["errors"] == {"backbone_key": "invalid_backbone_key"}

    secure_routing_manual = await hass.config_entries.flow.async_configure(
        result_invalid_key2["flow_id"],
        {
            CONF_KNX_ROUTING_BACKBONE_KEY: "bbaacc44bbaacc44bbaacc44bbaacc44",
            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
        },
    )
    assert secure_routing_manual["type"] is FlowResultType.CREATE_ENTRY
    assert secure_routing_manual["title"] == "Secure Routing as 0.0.123"
    assert secure_routing_manual["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING_SECURE,
        CONF_KNX_ROUTING_BACKBONE_KEY: "bbaacc44bbaacc44bbaacc44bbaacc44",
        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.123",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
    }
    knx_setup.assert_called_once()


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_routing_secure_keyfile(
    gateway_scanner_mock, hass: HomeAssistant, knx_setup
) -> None:
    """Test routing secure setup with keyfile."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "routing"
    assert result2["errors"] == {"base": "no_router_discovered"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3671,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.123",
            CONF_KNX_ROUTING_SECURE: True,
        },
    )
    assert result3["type"] is FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source_menu_routing"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == "secure_knxkeys"
    assert not result4["errors"]

    with patch_file_upload():
        routing_secure_knxkeys = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {
                CONF_KEYRING_FILE: FIXTURE_UPLOAD_UUID,
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
    assert routing_secure_knxkeys["type"] is FlowResultType.CREATE_ENTRY
    assert routing_secure_knxkeys["title"] == "Secure Routing as 0.0.123"
    assert routing_secure_knxkeys["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING_SECURE,
        CONF_KNX_KNXKEY_FILENAME: "knx/keyring.knxkeys",
        CONF_KNX_KNXKEY_PASSWORD: "password",
        CONF_KNX_ROUTING_BACKBONE_KEY: None,
        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: None,
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.123",
    }
    knx_setup.assert_called_once()


@pytest.mark.parametrize(
    ("user_input", "title", "config_entry_data"),
    [
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: False,
            },
            "Tunneling UDP @ 192.168.0.1",
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
                CONF_KNX_ROUTE_BACK: False,
                CONF_KNX_LOCAL_IP: None,
                CONF_KNX_TUNNEL_ENDPOINT_IA: None,
                CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
                CONF_KNX_SECURE_USER_ID: None,
                CONF_KNX_SECURE_USER_PASSWORD: None,
            },
        ),
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: False,
            },
            "Tunneling TCP @ 192.168.0.1",
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
                CONF_KNX_ROUTE_BACK: False,
                CONF_KNX_LOCAL_IP: None,
                CONF_KNX_TUNNEL_ENDPOINT_IA: None,
                CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
                CONF_KNX_SECURE_USER_ID: None,
                CONF_KNX_SECURE_USER_PASSWORD: None,
            },
        ),
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: True,
            },
            "Tunneling UDP @ 192.168.0.1",
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
                CONF_KNX_ROUTE_BACK: True,
                CONF_KNX_LOCAL_IP: None,
                CONF_KNX_TUNNEL_ENDPOINT_IA: None,
                CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
                CONF_KNX_SECURE_USER_ID: None,
                CONF_KNX_SECURE_USER_PASSWORD: None,
            },
        ),
    ],
)
@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_tunneling_setup_manual(
    gateway_scanner_mock: MagicMock,
    hass: HomeAssistant,
    knx_setup,
    user_input,
    title,
    config_entry_data,
) -> None:
    """Test tunneling if no gateway was found found (or `manual` option was chosen)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "manual_tunnel"
    assert result2["errors"] == {"base": "no_tunnel_discovered"}

    with patch(
        "homeassistant.components.knx.config_flow.request_description",
        return_value=_gateway_descriptor(
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            supports_tunnelling_tcp=(
                user_input[CONF_KNX_TUNNELING_TYPE] == CONF_KNX_TUNNELING_TCP
            ),
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input,
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == title
    assert result3["data"] == config_entry_data
    knx_setup.assert_called_once()


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_tunneling_setup_manual_request_description_error(
    gateway_scanner_mock: MagicMock,
    hass: HomeAssistant,
    knx_setup,
) -> None:
    """Test tunneling if no gateway was found found (or `manual` option was chosen)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert result["step_id"] == "manual_tunnel"
    assert result["errors"] == {"base": "no_tunnel_discovered"}

    # TCP configured but not supported by gateway
    with patch(
        "homeassistant.components.knx.config_flow.request_description",
        return_value=_gateway_descriptor(
            "192.168.0.1",
            3671,
            supports_tunnelling_tcp=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3671,
            },
        )
        assert result["step_id"] == "manual_tunnel"
        assert result["errors"] == {
            "base": "no_tunnel_discovered",
            "tunneling_type": "unsupported_tunnel_type",
        }
    # TCP configured but Secure required by gateway
    with patch(
        "homeassistant.components.knx.config_flow.request_description",
        return_value=_gateway_descriptor(
            "192.168.0.1",
            3671,
            supports_tunnelling_tcp=True,
            requires_secure=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3671,
            },
        )
        assert result["step_id"] == "manual_tunnel"
        assert result["errors"] == {
            "base": "no_tunnel_discovered",
            "tunneling_type": "unsupported_tunnel_type",
        }
    # Secure configured but not enabled on gateway
    with patch(
        "homeassistant.components.knx.config_flow.request_description",
        return_value=_gateway_descriptor(
            "192.168.0.1",
            3671,
            supports_tunnelling_tcp=True,
            requires_secure=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3671,
            },
        )
        assert result["step_id"] == "manual_tunnel"
        assert result["errors"] == {
            "base": "no_tunnel_discovered",
            "tunneling_type": "unsupported_tunnel_type",
        }
    # No connection to gateway
    with patch(
        "homeassistant.components.knx.config_flow.request_description",
        side_effect=CommunicationError(""),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3671,
            },
        )
        assert result["step_id"] == "manual_tunnel"
        assert result["errors"] == {"base": "cannot_connect"}
    # OK configuration
    with patch(
        "homeassistant.components.knx.config_flow.request_description",
        return_value=_gateway_descriptor(
            "192.168.0.1",
            3671,
            supports_tunnelling_tcp=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3671,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tunneling TCP @ 192.168.0.1"
    assert result["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 3671,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
    }
    knx_setup.assert_called_once()


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
@patch(
    "homeassistant.components.knx.config_flow.request_description",
    return_value=_gateway_descriptor("192.168.0.2", 3675),
)
async def test_tunneling_setup_for_local_ip(
    request_description_mock: MagicMock,
    gateway_scanner_mock: MagicMock,
    hass: HomeAssistant,
    knx_setup,
) -> None:
    """Test tunneling if only one gateway is found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
            "show_advanced_options": True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "manual_tunnel"
    assert result2["errors"] == {"base": "no_tunnel_discovered"}

    # invalid host ip address
    result_invalid_host = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: DEFAULT_MCAST_GRP,  # multicast addresses are invalid
            CONF_PORT: 3675,
            CONF_KNX_LOCAL_IP: "192.168.1.112",
        },
    )
    assert result_invalid_host["type"] is FlowResultType.FORM
    assert result_invalid_host["step_id"] == "manual_tunnel"
    assert result_invalid_host["errors"] == {
        CONF_HOST: "invalid_ip_address",
        "base": "no_tunnel_discovered",
    }
    # invalid local ip address
    result_invalid_local = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.0.2",
            CONF_PORT: 3675,
            CONF_KNX_LOCAL_IP: "asdf",
        },
    )
    assert result_invalid_local["type"] is FlowResultType.FORM
    assert result_invalid_local["step_id"] == "manual_tunnel"
    assert result_invalid_local["errors"] == {
        CONF_KNX_LOCAL_IP: "invalid_ip_address",
        "base": "no_tunnel_discovered",
    }

    # valid user input
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.0.2",
            CONF_PORT: 3675,
            CONF_KNX_LOCAL_IP: "192.168.1.112",
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Tunneling UDP @ 192.168.0.2"
    assert result3["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        CONF_HOST: "192.168.0.2",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_LOCAL_IP: "192.168.1.112",
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
    }
    knx_setup.assert_called_once()


async def test_tunneling_setup_for_multiple_found_gateways(
    hass: HomeAssistant, knx_setup
) -> None:
    """Test tunneling if multiple gateways are found."""
    gateway_udp = _gateway_descriptor("192.168.0.1", 3675)
    gateway_tcp = _gateway_descriptor("192.168.1.100", 3675, True)
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock(
            [gateway_udp, gateway_tcp]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]

    tunnel_flow = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert tunnel_flow["type"] is FlowResultType.FORM
    assert tunnel_flow["step_id"] == "tunnel"
    assert not tunnel_flow["errors"]

    result = await hass.config_entries.flow.async_configure(
        tunnel_flow["flow_id"],
        {CONF_KNX_GATEWAY: str(gateway_udp)},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
    }
    knx_setup.assert_called_once()


async def test_tunneling_setup_tcp_endpoint_select_skip(
    hass: HomeAssistant, knx_setup
) -> None:
    """Test tunneling TCP endpoint selection skipped if no slot info found."""
    gateway_udp = _gateway_descriptor("192.168.0.1", 3675)
    gateway_tcp_no_slots = _gateway_descriptor("192.168.1.100", 3675, True, slots=False)
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock(
            [gateway_udp, gateway_tcp_no_slots]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]

    tunnel_flow = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert tunnel_flow["type"] is FlowResultType.FORM
    assert tunnel_flow["step_id"] == "tunnel"
    assert not tunnel_flow["errors"]

    result = await hass.config_entries.flow.async_configure(
        tunnel_flow["flow_id"],
        {CONF_KNX_GATEWAY: str(gateway_tcp_no_slots)},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
    }
    knx_setup.assert_called_once()


async def test_tunneling_setup_tcp_endpoint_select(
    hass: HomeAssistant, knx_setup
) -> None:
    """Test tunneling TCP endpoint selection."""
    gateway_tcp = _gateway_descriptor("192.168.1.100", 3675, True)
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway_tcp])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]

    tunnel_flow = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert tunnel_flow["type"] is FlowResultType.FORM
    assert tunnel_flow["step_id"] == "tunnel"
    assert not tunnel_flow["errors"]

    endpoint_flow = await hass.config_entries.flow.async_configure(
        tunnel_flow["flow_id"],
        {CONF_KNX_GATEWAY: str(gateway_tcp)},
    )

    assert endpoint_flow["type"] is FlowResultType.FORM
    assert endpoint_flow["step_id"] == "tcp_tunnel_endpoint"
    assert not endpoint_flow["errors"]

    result = await hass.config_entries.flow.async_configure(
        endpoint_flow["flow_id"],
        {CONF_KNX_TUNNEL_ENDPOINT_IA: "1.0.242"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.0.242 @ 1.0.0 - Test @ 192.168.1.100:3675"
    assert result["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_TUNNEL_ENDPOINT_IA: "1.0.242",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
    }
    knx_setup.assert_called_once()


@pytest.mark.parametrize(
    "gateway",
    [
        _gateway_descriptor("192.168.0.1", 3675),
        _gateway_descriptor("192.168.0.1", 3675, supports_tunnelling_tcp=True),
        _gateway_descriptor(
            "192.168.0.1", 3675, supports_tunnelling_tcp=True, requires_secure=True
        ),
    ],
)
async def test_manual_tunnel_step_with_found_gateway(
    hass: HomeAssistant, gateway
) -> None:
    """Test manual tunnel if gateway was found and tunneling is selected."""
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]

    tunnel_flow = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert tunnel_flow["type"] is FlowResultType.FORM
    assert tunnel_flow["step_id"] == "tunnel"
    assert not tunnel_flow["errors"]

    manual_tunnel_flow = await hass.config_entries.flow.async_configure(
        tunnel_flow["flow_id"],
        {
            CONF_KNX_GATEWAY: OPTION_MANUAL_TUNNEL,
        },
    )
    assert manual_tunnel_flow["type"] is FlowResultType.FORM
    assert manual_tunnel_flow["step_id"] == "manual_tunnel"
    assert not manual_tunnel_flow["errors"]


async def test_form_with_automatic_connection_handling(
    hass: HomeAssistant, knx_setup
) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock(
            [_gateway_descriptor("192.168.0.1", 3675)]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CONF_KNX_AUTOMATIC.capitalize()
    assert result2["data"] == {
        # don't use **DEFAULT_ENTRY_DATA here to check for correct usage of defaults
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_LOCAL_IP: None,
        CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
        CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
        CONF_KNX_RATE_LIMIT: 0,
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
        CONF_KNX_STATE_UPDATER: True,
        CONF_KNX_TELEGRAM_LOG_SIZE: 1000,
    }
    knx_setup.assert_called_once()


async def _get_menu_step_secure_tunnel(hass: HomeAssistant) -> FlowResult:
    """Return flow in secure_tunnelling menu step."""
    gateway = _gateway_descriptor(
        "192.168.0.1",
        3675,
        supports_tunnelling_tcp=True,
        requires_secure=True,
    )
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "tunnel"
    assert not result2["errors"]

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_KNX_GATEWAY: str(gateway)},
    )
    assert result3["type"] is FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source_menu_tunnel"
    return result3


@patch(
    "homeassistant.components.knx.config_flow.request_description",
    return_value=_gateway_descriptor(
        "192.168.0.1",
        3675,
        supports_tunnelling_tcp=True,
        requires_secure=True,
    ),
)
async def test_get_secure_menu_step_manual_tunnelling(
    request_description_mock: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Test flow reaches secure_tunnellinn menu step from manual tunnelling configuration."""
    gateway = _gateway_descriptor(
        "192.168.0.1",
        3675,
        supports_tunnelling_tcp=True,
        requires_secure=True,
    )
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "tunnel"
    assert not result2["errors"]

    manual_tunnel_flow = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_GATEWAY: OPTION_MANUAL_TUNNEL,
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        manual_tunnel_flow["flow_id"],
        {
            CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
        },
    )
    assert result3["type"] is FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source_menu_tunnel"


async def test_configure_secure_tunnel_manual(hass: HomeAssistant, knx_setup) -> None:
    """Test configure tunnelling secure keys manually."""
    menu_step = await _get_menu_step_secure_tunnel(hass)

    result = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_tunnel_manual"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "secure_tunnel_manual"
    assert not result["errors"]

    secure_tunnel_manual = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_SECURE_USER_ID: 2,
            CONF_KNX_SECURE_USER_PASSWORD: "password",
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_auth",
        },
    )
    assert secure_tunnel_manual["type"] is FlowResultType.CREATE_ENTRY
    assert secure_tunnel_manual["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
        CONF_KNX_SECURE_USER_ID: 2,
        CONF_KNX_SECURE_USER_PASSWORD: "password",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_auth",
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_LOCAL_IP: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
    }
    knx_setup.assert_called_once()


async def test_configure_secure_knxkeys(hass: HomeAssistant, knx_setup) -> None:
    """Test configure secure knxkeys."""
    menu_step = await _get_menu_step_secure_tunnel(hass)

    result = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "secure_knxkeys"
    assert not result["errors"]

    with patch_file_upload():
        secure_knxkeys = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEYRING_FILE: FIXTURE_UPLOAD_UUID,
                CONF_KNX_KNXKEY_PASSWORD: "test",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert secure_knxkeys["step_id"] == "knxkeys_tunnel_select"
    assert not result["errors"]
    secure_knxkeys = await hass.config_entries.flow.async_configure(
        secure_knxkeys["flow_id"],
        {CONF_KNX_TUNNEL_ENDPOINT_IA: CONF_KNX_AUTOMATIC},
    )

    assert secure_knxkeys["type"] is FlowResultType.CREATE_ENTRY
    assert secure_knxkeys["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
        CONF_KNX_KNXKEY_FILENAME: "knx/keyring.knxkeys",
        CONF_KNX_KNXKEY_PASSWORD: "test",
        CONF_KNX_ROUTING_BACKBONE_KEY: None,
        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: None,
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_LOCAL_IP: None,
    }
    knx_setup.assert_called_once()


async def test_configure_secure_knxkeys_invalid_signature(hass: HomeAssistant) -> None:
    """Test configure secure knxkeys but file was not found."""
    menu_step = await _get_menu_step_secure_tunnel(hass)

    result = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "secure_knxkeys"
    assert not result["errors"]

    with patch_file_upload(
        side_effect=InvalidSecureConfiguration(),
    ):
        secure_knxkeys = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEYRING_FILE: FIXTURE_UPLOAD_UUID,
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
        assert secure_knxkeys["type"] is FlowResultType.FORM
        assert secure_knxkeys["errors"]
        assert (
            secure_knxkeys["errors"][CONF_KNX_KNXKEY_PASSWORD]
            == "keyfile_invalid_signature"
        )


async def test_configure_secure_knxkeys_no_tunnel_for_host(hass: HomeAssistant) -> None:
    """Test configure secure knxkeys but file was not found."""
    menu_step = await _get_menu_step_secure_tunnel(hass)

    result = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "secure_knxkeys"
    assert not result["errors"]

    with patch_file_upload(return_value=Mock()) as mock_keyring:
        mock_keyring.get_tunnel_interfaces_by_host.return_value = []
        secure_knxkeys = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEYRING_FILE: FIXTURE_UPLOAD_UUID,
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
        assert secure_knxkeys["type"] is FlowResultType.FORM
        assert secure_knxkeys["errors"] == {"base": "keyfile_no_tunnel_for_host"}


async def test_options_flow_connection_type(
    hass: HomeAssistant, knx, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow changing interface."""
    # run one option flow test with a set up integration (knx fixture)
    # instead of mocking async_setup_entry (knx_setup fixture) to test
    # usage of the already running XKNX instance for gateway scanner
    gateway = _gateway_descriptor("192.168.0.1", 3675)

    await knx.setup_integration({})
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.options.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "connection_type"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "connection_type"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "tunnel"

        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={
                CONF_KNX_GATEWAY: str(gateway),
            },
        )
        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert not result3["data"]
        assert mock_config_entry.data == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_LOCAL_IP: None,
            CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_RATE_LIMIT: 0,
            CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_TUNNEL_ENDPOINT_IA: None,
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
            CONF_KNX_SECURE_USER_ID: None,
            CONF_KNX_SECURE_USER_PASSWORD: None,
            CONF_KNX_TELEGRAM_LOG_SIZE: 1000,
        }


async def test_options_flow_secure_manual_to_keyfile(
    hass: HomeAssistant, knx_setup
) -> None:
    """Test options flow changing secure credential source."""
    mock_config_entry = MockConfigEntry(
        title="KNX",
        domain="knx",
        data={
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
            CONF_KNX_SECURE_USER_ID: 2,
            CONF_KNX_SECURE_USER_PASSWORD: "password",
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_auth",
            CONF_KNX_KNXKEY_FILENAME: "knx/testcase.knxkeys",
            CONF_KNX_KNXKEY_PASSWORD: "invalid_password",
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_LOCAL_IP: None,
        },
    )
    gateway = _gateway_descriptor(
        "192.168.0.1",
        3675,
        supports_tunnelling_tcp=True,
        requires_secure=True,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.options.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "connection_type"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "connection_type"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "tunnel"
        assert not result2["errors"]

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        {CONF_KNX_GATEWAY: str(gateway)},
    )
    assert result3["type"] is FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source_menu_tunnel"

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == "secure_knxkeys"
    assert not result4["errors"]

    with patch_file_upload():
        secure_knxkeys = await hass.config_entries.options.async_configure(
            result4["flow_id"],
            {
                CONF_KEYRING_FILE: FIXTURE_UPLOAD_UUID,
                CONF_KNX_KNXKEY_PASSWORD: "test",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert secure_knxkeys["step_id"] == "knxkeys_tunnel_select"
    assert not result["errors"]
    secure_knxkeys = await hass.config_entries.options.async_configure(
        secure_knxkeys["flow_id"],
        {CONF_KNX_TUNNEL_ENDPOINT_IA: "1.0.1"},
    )

    assert secure_knxkeys["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.data == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
        CONF_KNX_KNXKEY_FILENAME: "knx/keyring.knxkeys",
        CONF_KNX_KNXKEY_PASSWORD: "test",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: "1.0.1",
        CONF_KNX_ROUTING_BACKBONE_KEY: None,
        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: None,
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_LOCAL_IP: None,
    }
    knx_setup.assert_called_once()


async def test_options_flow_routing(hass: HomeAssistant, knx_setup) -> None:
    """Test options flow changing routing settings."""
    mock_config_entry = MockConfigEntry(
        title="KNX",
        domain="knx",
        data={
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    gateway = _gateway_descriptor("192.168.0.1", 3676)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.options.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "connection_type"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "connection_type"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "routing"
        assert result2["errors"] == {}

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_INDIVIDUAL_ADDRESS: "2.0.4",
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.data == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
        CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
        CONF_KNX_LOCAL_IP: None,
        CONF_KNX_INDIVIDUAL_ADDRESS: "2.0.4",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: None,
    }
    knx_setup.assert_called_once()


async def test_options_communication_settings(
    hass: HomeAssistant, knx_setup, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow changing communication settings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "communication_settings"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "communication_settings"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_KNX_STATE_UPDATER: False,
            CONF_KNX_RATE_LIMIT: 40,
            CONF_KNX_TELEGRAM_LOG_SIZE: 3000,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert not result2.get("data")
    assert mock_config_entry.data == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
        CONF_KNX_STATE_UPDATER: False,
        CONF_KNX_RATE_LIMIT: 40,
        CONF_KNX_TELEGRAM_LOG_SIZE: 3000,
    }
    knx_setup.assert_called_once()


async def test_options_update_keyfile(hass: HomeAssistant, knx_setup) -> None:
    """Test options flow updating keyfile when tunnel endpoint is already configured."""
    start_data = {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
        CONF_KNX_SECURE_USER_ID: 2,
        CONF_KNX_SECURE_USER_PASSWORD: "password",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_auth",
        CONF_KNX_KNXKEY_PASSWORD: "old_password",
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_LOCAL_IP: None,
        CONF_KNX_TUNNEL_ENDPOINT_IA: "1.0.1",
    }
    mock_config_entry = MockConfigEntry(
        title="KNX",
        domain="knx",
        data=start_data,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "secure_knxkeys"

    with patch_file_upload():
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_KEYRING_FILE: FIXTURE_UPLOAD_UUID,
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert not result2.get("data")
    assert mock_config_entry.data == {
        **start_data,
        CONF_KNX_KNXKEY_FILENAME: "knx/keyring.knxkeys",
        CONF_KNX_KNXKEY_PASSWORD: "password",
        CONF_KNX_ROUTING_BACKBONE_KEY: None,
        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: None,
    }
    knx_setup.assert_called_once()


async def test_options_keyfile_upload(hass: HomeAssistant, knx_setup) -> None:
    """Test options flow uploading a keyfile for the first time."""
    start_data = {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_LOCAL_IP: None,
    }
    mock_config_entry = MockConfigEntry(
        title="KNX",
        domain="knx",
        data=start_data,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "secure_knxkeys"

    with patch_file_upload():
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_KEYRING_FILE: FIXTURE_UPLOAD_UUID,
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "knxkeys_tunnel_select"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_KNX_TUNNEL_ENDPOINT_IA: "1.0.1",
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert not result3.get("data")
    assert mock_config_entry.data == {
        **start_data,
        CONF_KNX_KNXKEY_FILENAME: "knx/keyring.knxkeys",
        CONF_KNX_KNXKEY_PASSWORD: "password",
        CONF_KNX_TUNNEL_ENDPOINT_IA: "1.0.1",
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_ROUTING_BACKBONE_KEY: None,
        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: None,
    }
    knx_setup.assert_called_once()
