"""Tests for the Mikrotik coordinator."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.mikrotik.const import (
    CAPSMAN,
    DHCP,
    INTERFACE,
    MIKROTIK_SERVICES,
    WIFI,
)
from homeassistant.components.mikrotik.coordinator import MikrotikData, get_api
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .conftest import MockCommandResponses, MockConfigEntryFactory
from .const import (
    ARP_DATA,
    BRIDGE1_INTERFACE,
    DEVICE_1_DHCP,
    DEVICE_1_WIRELESS,
    DEVICE_2_DHCP,
    DEVICE_2_WIRELESS,
    ETHER1_INTERFACE,
    MOCK_DATA,
)


@pytest.mark.parametrize(
    ("support_attr", "service_const", "wireless_device", "dhcp_device"),
    [
        pytest.param(
            "support_capsman",
            CAPSMAN,
            DEVICE_1_WIRELESS,
            DEVICE_1_DHCP,
            id="capsman",
        ),
        pytest.param(
            "support_wifi",
            WIFI,
            DEVICE_2_WIRELESS,
            DEVICE_2_DHCP,
            id="wifi",
        ),
    ],
)
async def test_update_devices_uses_wireless_service_when_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntryFactory,
    mock_api: MagicMock,
    mock_command_responses: MockCommandResponses,
    support_attr: str,
    service_const: str,
    wireless_device: dict[str, Any],
    dhcp_device: dict[str, Any],
) -> None:
    """Test update_devices lists devices from the supported wireless service."""
    mikrotik_data = MikrotikData(hass, mock_config_entry(), mock_api)
    setattr(mikrotik_data, support_attr, True)

    mock_command_responses[MIKROTIK_SERVICES[service_const]] = [wireless_device]
    mock_command_responses[MIKROTIK_SERVICES[DHCP]] = [dhcp_device]

    mikrotik_data.update_devices()

    mac = dhcp_device["mac-address"]
    assert mikrotik_data.devices[mac].last_seen is not None


async def test_update_devices_skips_loopback_interfaces(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntryFactory,
    mock_api: MagicMock,
    mock_command_responses: MockCommandResponses,
) -> None:
    """Test loopback interfaces are excluded from the interface list."""
    mikrotik_data = MikrotikData(hass, mock_config_entry(), mock_api)

    loopback_interface = {**BRIDGE1_INTERFACE, "name": "lo", "type": "loopback"}
    mock_command_responses[MIKROTIK_SERVICES[INTERFACE]] = [
        ETHER1_INTERFACE,
        loopback_interface,
    ]

    mikrotik_data.update_devices()

    assert [interf["name"] for interf in mikrotik_data.interfaces] == ["ether1"]


async def test_update_devices_wired_device_without_active_address_is_inactive(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntryFactory,
    mock_api: MagicMock,
    mock_command_responses: MockCommandResponses,
) -> None:
    """Test a wired device without an active-address is marked inactive."""
    mikrotik_data = MikrotikData(hass, mock_config_entry(), mock_api)

    device = {k: v for k, v in DEVICE_1_DHCP.items() if k != "active-address"}
    mock_command_responses[MIKROTIK_SERVICES[DHCP]] = [device]

    mikrotik_data.update_devices()

    mac = DEVICE_1_DHCP["mac-address"]
    assert mikrotik_data.devices[mac].last_seen is None


@pytest.mark.parametrize(
    ("ping_replies", "expected_result"),
    [
        pytest.param(
            [{"seq": "0"}, {"seq": "1"}, {"seq": "2"}],
            True,
            id="reply_received",
        ),
        pytest.param(
            [
                {"status": "timeout"},
                {"status": "timeout"},
                {"status": "timeout"},
            ],
            False,
            id="all_timed_out",
        ),
    ],
)
async def test_do_arp_ping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntryFactory,
    mock_api: MagicMock,
    ping_replies: list[dict[str, Any]],
    expected_result: bool,
) -> None:
    """Test do_arp_ping reflects whether any ping reply was received in time."""
    mikrotik_data = MikrotikData(hass, mock_config_entry(), mock_api)
    mock_api.return_value = ping_replies

    ip_address = DEVICE_1_DHCP["address"]
    interface = ARP_DATA[0]["interface"]
    assert mikrotik_data.do_arp_ping(ip_address, interface) is expected_result


async def test_get_api_wraps_connection_with_ssl_when_verify_ssl_enabled() -> None:
    """Test get_api wraps the connection in an SSL context when verify_ssl is set."""
    entry_data = {**MOCK_DATA, CONF_VERIFY_SSL: True}

    with patch("librouteros.connect", return_value=MagicMock()) as mock_connect:
        get_api(entry_data)

    assert "ssl_wrapper" in mock_connect.call_args.kwargs
