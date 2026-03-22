"""Tests for the SNMP coordinator."""

import binascii
from unittest.mock import Mock, patch

from pysnmp.error import PySnmpError
from pysnmp.proto.rfc1902 import OctetString
import pytest

from homeassistant.components.snmp.const import DOMAIN
from homeassistant.components.snmp.coordinator import SnmpUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_request_args():
    """Mock request arguments for the coordinator."""
    return (
        Mock(),  # engine
        Mock(),  # auth_data
        Mock(),  # target
        Mock(),  # context_data
        Mock(),  # object_type
    )


async def test_coordinator_mac_normalization(
    hass: HomeAssistant, mock_request_args
) -> None:
    """Test MAC address normalization with various formats."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.1.1.1"})
    coordinator = SnmpUpdateCoordinator(hass, entry, mock_request_args)
    coordinator.model = "Test"

    # Test cases: (input_octets, expected_mac)
    test_cases = [
        (binascii.unhexlify("001122334455"), "00:11:22:33:44:55"),  # Binary
        (b"00:11:22:33:44:66", "00:11:22:33:44:66"),  # Colon string
        (b"00-11-22-33-44-77", "00:11:22:33:44:77"),  # Dash string
        (b"0011.2233.4488", "00:11:22:33:44:88"),  # Dot string
        (b"00 11 22 33 44 99", "00:11:22:33:44:99"),  # Space string
        (b"ABCDEFABCDEF", "ab:cd:ef:ab:cd:ef"),  # Raw hex string
    ]

    for input_bytes, expected_mac in test_cases:
        oid = Mock()
        oid.asTuple.return_value = (1, 1, 1, 1, 0)  # Dummy OID
        val = OctetString(input_bytes)

        async def mock_walk(*args, o=oid, v=val, **kwargs):
            yield None, None, None, [(o, v)]

        with patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ):
            data = await coordinator._async_update_data()
            assert expected_mac in data


async def test_coordinator_ip_extraction(
    hass: HomeAssistant, mock_request_args
) -> None:
    """Test IP address extraction from OID suffix."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.1.1.1"})
    coordinator = SnmpUpdateCoordinator(hass, entry, mock_request_args)
    coordinator.model = "Test"

    mac_bytes = binascii.unhexlify("001122334455")
    mac_str = "00:11:22:33:44:55"

    # Test cases: (oid_tuple, expected_ip)
    test_cases = [
        ((1, 3, 6, 1, 2, 1, 4, 22, 1, 6, 1, 192, 168, 1, 10), "192.168.1.10"),
        ((1, 1, 1, 1, 10, 20, 30, 40), "10.20.30.40"),
        ((1, 2, 3), "0.0.0.0"),  # OID too short
    ]

    for oid_tuple, expected_ip in test_cases:
        oid = Mock()
        oid.asTuple.return_value = oid_tuple
        val = OctetString(mac_bytes)

        async def mock_walk(*args, o=oid, v=val, **kwargs):
            yield None, None, None, [(o, v)]

        with patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ):
            data = await coordinator._async_update_data()
            assert data[mac_str] == expected_ip


async def test_coordinator_walk_error(hass: HomeAssistant, mock_request_args) -> None:
    """Test handling of PySnmpError during walk iteration."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.1.1.1"})
    coordinator = SnmpUpdateCoordinator(hass, entry, mock_request_args)
    coordinator.model = "Test"

    async def mock_walk_error(*args, **kwargs):
        """Simulate an error raised during iteration."""
        if kwargs is not None:
            raise PySnmpError("Network unreachable")
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk_error,
        ),
        pytest.raises(
            UpdateFailed, match="SNMP error during walk: Network unreachable"
        ),
    ):
        await coordinator._async_update_data()


async def test_coordinator_host_info_error(
    hass: HomeAssistant, mock_request_args
) -> None:
    """Test handling of PySnmpError during host info fetching."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.1.1.1"})
    coordinator = SnmpUpdateCoordinator(hass, entry, mock_request_args)

    with patch(
        "homeassistant.components.snmp.coordinator.get_cmd",
        side_effect=PySnmpError("Connection timed out"),
    ):
        await coordinator._async_fetch_host_info()
        assert coordinator.model == ""  # Should be set to empty string to prevent retry


async def test_coordinator_walk_errindication(
    hass: HomeAssistant, mock_request_args
) -> None:
    """Test handling of errindication (string vs exception) during walk."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.1.1.1"})
    coordinator = SnmpUpdateCoordinator(hass, entry, mock_request_args)
    coordinator.model = "Test"

    # 1. Test errindication as a string
    async def mock_walk_string_error(*args, **kwargs):
        yield "timeout", None, None, []

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk_string_error,
        ),
        pytest.raises(UpdateFailed, match="SNMPLIB error: timeout") as excinfo,
    ):
        await coordinator._async_update_data()
    assert excinfo.value.__cause__ is None

    # 2. Test errindication as an exception
    exc = PySnmpError("Some error")

    async def mock_walk_exception_error(*args, **kwargs):
        yield exc, None, None, []

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk_exception_error,
        ),
        pytest.raises(UpdateFailed, match="SNMPLIB error: Some error") as excinfo,
    ):
        await coordinator._async_update_data()
    assert excinfo.value.__cause__ is exc
