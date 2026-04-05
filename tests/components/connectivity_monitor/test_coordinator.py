"""Tests for the Connectivity Monitor coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.connectivity_monitor.const import (
    CONF_BLUETOOTH_ADDRESS,
    CONF_ESPHOME_DEVICE_ID,
    CONF_HOST,
    CONF_MATTER_NODE_ID,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_ZHA_IEEE,
    DEFAULT_DNS_SERVER,
    DOMAIN,
    PROTOCOL_AD_DC,
    PROTOCOL_BLUETOOTH,
    PROTOCOL_ESPHOME,
    PROTOCOL_ICMP,
    PROTOCOL_MATTER,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
    PROTOCOL_ZHA,
)
from homeassistant.components.connectivity_monitor.coordinator import (
    ConnectivityMonitorCoordinator,
    _target_key,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _create_coordinator(
    hass: HomeAssistant, targets: list[dict[str, str | int]]
) -> ConnectivityMonitorCoordinator:
    """Create a coordinator for direct coordinator tests."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Network Monitor",
        unique_id="connectivity_monitor_network",
        version=2,
        data={},
    )

    return ConnectivityMonitorCoordinator(
        hass=hass,
        targets=targets,
        update_interval=30,
        dns_server=DEFAULT_DNS_SERVER,
        config_entry=config_entry,
    )


@pytest.mark.parametrize(
    ("target", "expected_key"),
    [
        (
            {CONF_PROTOCOL: PROTOCOL_TCP, CONF_HOST: "192.168.1.1", CONF_PORT: 443},
            "TCP:192.168.1.1:443",
        ),
        (
            {CONF_PROTOCOL: PROTOCOL_UDP, CONF_HOST: "192.168.1.1", CONF_PORT: 53},
            "UDP:192.168.1.1:53",
        ),
        (
            {
                CONF_PROTOCOL: PROTOCOL_AD_DC,
                CONF_HOST: "192.168.1.2",
                CONF_PORT: 389,
            },
            "AD_DC:192.168.1.2:389",
        ),
        ({CONF_PROTOCOL: PROTOCOL_ICMP, CONF_HOST: "192.168.1.3"}, "ICMP:192.168.1.3"),
        (
            {CONF_PROTOCOL: PROTOCOL_ZHA, CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77"},
            "ZHA:00:11:22:33:44:55:66:77",
        ),
        (
            {CONF_PROTOCOL: PROTOCOL_MATTER, CONF_MATTER_NODE_ID: "1-1234"},
            "MATTER:1-1234",
        ),
        (
            {CONF_PROTOCOL: PROTOCOL_ESPHOME, CONF_ESPHOME_DEVICE_ID: "node-1"},
            "ESPHOME:node-1",
        ),
        (
            {
                CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
                CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
            },
            "BLUETOOTH:AA:BB:CC:DD:EE:FF",
        ),
        (
            {CONF_PROTOCOL: "CUSTOM", CONF_HOST: "custom-target"},
            "CUSTOM:custom-target",
        ),
    ],
)
def test_target_key_builds_expected_identifier(
    target: dict[str, str | int], expected_key: str
) -> None:
    """Test protocol-specific target keys are stable and unique."""
    assert _target_key(target) == expected_key


@pytest.mark.parametrize(
    ("target", "expected_result"),
    [
        (
            {CONF_PROTOCOL: PROTOCOL_ICMP, CONF_HOST: "192.168.1.1"},
            {
                "connected": False,
                "latency": None,
                "resolved_ip": None,
                "mac_address": None,
            },
        ),
        (
            {CONF_PROTOCOL: PROTOCOL_ZHA, CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77"},
            {"active": False, "device_found": False},
        ),
    ],
)
def test_default_result_for_protocol_family(
    hass: HomeAssistant,
    target: dict[str, str | int],
    expected_result: dict[str, bool | None],
) -> None:
    """Test protocol families get the expected empty payload shape."""
    coordinator = _create_coordinator(hass, [target])

    assert coordinator._default_result_for(target) == expected_result


async def test_get_target_data_returns_payload_for_known_target(
    hass: HomeAssistant,
) -> None:
    """Test get_target_data returns the stored payload for a known target."""
    target = {CONF_PROTOCOL: PROTOCOL_ICMP, CONF_HOST: "192.168.1.1"}
    coordinator = _create_coordinator(hass, [target])
    coordinator.data = {_target_key(target): {"connected": True, "latency": 7.5}}

    assert coordinator.get_target_data(target) == {"connected": True, "latency": 7.5}
    assert (
        coordinator.get_target_data(
            {CONF_PROTOCOL: PROTOCOL_ICMP, CONF_HOST: "192.168.1.9"}
        )
        == {}
    )


async def test_async_update_data_mixes_success_and_failures(
    hass: HomeAssistant,
) -> None:
    """Test one polling cycle preserves good results and falls back failed ones."""
    targets: list[dict[str, str | int]] = [
        {CONF_PROTOCOL: PROTOCOL_ICMP, CONF_HOST: "192.168.1.1"},
        {CONF_PROTOCOL: PROTOCOL_TCP, CONF_HOST: "192.168.1.1", CONF_PORT: 443},
        {CONF_PROTOCOL: PROTOCOL_ZHA, CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77"},
    ]
    coordinator = _create_coordinator(hass, targets)

    with (
        patch.object(
            coordinator._network_probe,
            "async_prepare_host",
            AsyncMock(return_value=None),
        ) as mock_prepare_host,
        patch.object(
            coordinator,
            "_async_update_target",
            AsyncMock(
                side_effect=[
                    {
                        "connected": True,
                        "latency": 5.0,
                        "resolved_ip": "192.168.1.1",
                        "mac_address": None,
                    },
                    {
                        "connected": True,
                        "latency": 2.5,
                        "resolved_ip": "192.168.1.1",
                        "mac_address": None,
                    },
                    RuntimeError("probe failed"),
                ]
            ),
        ),
    ):
        result = await coordinator._async_update_data()

    mock_prepare_host.assert_awaited_once_with("192.168.1.1")
    assert result == {
        "ICMP:192.168.1.1": {
            "connected": True,
            "latency": 5.0,
            "resolved_ip": "192.168.1.1",
            "mac_address": None,
        },
        "TCP:192.168.1.1:443": {
            "connected": True,
            "latency": 2.5,
            "resolved_ip": "192.168.1.1",
            "mac_address": None,
        },
        "ZHA:00:11:22:33:44:55:66:77": {"active": False, "device_found": False},
    }


async def test_async_update_target_uses_network_probe_for_network_protocols(
    hass: HomeAssistant,
) -> None:
    """Test network protocols are delegated to the shared network probe."""
    target = {CONF_PROTOCOL: PROTOCOL_TCP, CONF_HOST: "192.168.1.1", CONF_PORT: 443}
    coordinator = _create_coordinator(hass, [target])

    with patch.object(
        coordinator._network_probe,
        "async_update_target",
        AsyncMock(return_value={"connected": True}),
    ) as mock_update_target:
        result = await coordinator._async_update_target(target)

    assert result == {"connected": True}
    mock_update_target.assert_awaited_once_with(target)


async def test_async_update_target_returns_default_for_unsupported_protocol(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test unsupported protocols log and return a safe default payload."""
    target = {CONF_PROTOCOL: "CUSTOM", CONF_HOST: "custom-target"}
    coordinator = _create_coordinator(hass, [target])

    result = await coordinator._async_update_target(target)

    assert result == {
        "connected": False,
        "latency": None,
        "resolved_ip": None,
        "mac_address": None,
    }
    assert "Unsupported protocol 'CUSTOM'" in caplog.text
