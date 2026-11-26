"""Tests configuration for Govee Local API."""

import asyncio
from collections.abc import Generator
from ipaddress import IPv4Network
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.govee_light_local.coordinator import GoveeController

from . import NETWORK_ADAPTERS, scan_reply


@pytest.fixture(name="mock_network_adapters")
def fixture_mock_network_adapters() -> Generator[None]:
    """Mock a host with two enabled adapters and one disabled adapter."""
    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=NETWORK_ADAPTERS,
    ):
        yield


@pytest.fixture(autouse=True)
def fixture_no_discovery_wait() -> Generator[None]:
    """Do not wait for scan replies; the mocked lamps answer right away."""
    with patch(
        "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT", 0
    ):
        yield


@pytest.fixture(name="mock_govee_api")
def fixture_mock_govee_api() -> Generator[AsyncMock]:
    """Set up Govee Local API fixture."""
    mock_api = AsyncMock(spec=GoveeController)
    mock_api.start = AsyncMock()
    mock_api.cleanup = MagicMock(return_value=asyncio.Event())
    mock_api.cleanup.return_value.set()
    mock_api.turn_on_off = AsyncMock()
    mock_api.set_brightness = AsyncMock()
    mock_api.set_color = AsyncMock()
    mock_api.set_scene = AsyncMock()
    mock_api._async_update_data = AsyncMock()
    # The library strips the mask off the address it stores, and keeps the
    # parsed network in a separate index-aligned list.
    mock_api.listening_addresses = ["10.0.0.7", "192.168.1.2"]
    mock_api.networks = [IPv4Network("10.0.0.0/8"), IPv4Network("192.168.1.0/24")]
    mock_api.bind_failures = []
    mock_api.protocols = [MagicMock()]
    mock_api.rebind_failed = AsyncMock(return_value=[])
    mock_api.devices = []
    mock_api.answering_devices = []
    mock_api.get_device_by_fingerprint = MagicMock(
        side_effect=lambda fingerprint: next(
            (
                device
                for device in mock_api.devices
                if device.fingerprint == fingerprint
            ),
            None,
        )
    )
    mock_api.get_device_by_ip = MagicMock(
        side_effect=lambda ip: next(
            (device for device in mock_api.devices if device.ip == ip), None
        )
    )
    mock_api.remove_device = MagicMock(
        side_effect=lambda device: (
            mock_api.devices.remove(device) if device in mock_api.devices else None
        )
    )
    mock_api.probe_only_devices = []
    mock_api.discovery_queue = set()
    mock_api.add_device_to_discovery_queue = MagicMock(
        side_effect=mock_api.discovery_queue.add
    )
    mock_api.remove_device_from_discovery_queue = MagicMock(
        side_effect=mock_api.discovery_queue.discard
    )
    mock_api.send_discovery_message = MagicMock(
        side_effect=lambda: [
            scan_reply(mock_api, device)
            for device in (
                *mock_api.answering_devices,
                # Reached by a scan sent to their address, not by the multicast one.
                *(
                    device
                    for device in mock_api.probe_only_devices
                    if device.ip in mock_api.discovery_queue or device.is_manual
                ),
            )
        ]
    )

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_api,
    ) as mock_controller:
        yield mock_controller.return_value


@pytest.fixture(name="mock_stuck_cleanup")
def fixture_mock_stuck_cleanup(mock_govee_api: AsyncMock) -> None:
    """Make cleanup never complete, as if a transport never closed."""
    mock_govee_api.cleanup = MagicMock(return_value=asyncio.Event())


@pytest.fixture(name="mock_setup_entry")
def fixture_mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.govee_light_local.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry
