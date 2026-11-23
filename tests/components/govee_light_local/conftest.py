"""Tests configuration for Govee Local API."""

import asyncio
from collections.abc import Generator
from ipaddress import IPv4Network
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from govee_local_api import GoveeDevice, GoveeLightCapabilities, GoveeLightFeatures
from govee_local_api.device_registry import DeviceRegistry
from govee_local_api.light_capabilities import COMMON_FEATURES, SCENE_CODES
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.components.govee_light_local.coordinator import GoveeController
from homeassistant.components.network import Adapter
from homeassistant.core import HomeAssistant

NETWORK_ADAPTERS: list[Adapter] = [
    {
        "name": "eth0",
        "index": 1,
        "enabled": True,
        "auto": True,
        "default": True,
        # The same address twice, to check it is only listened on once.
        "ipv4": [
            {"address": "192.168.1.2", "network_prefix": 24},
            {"address": "192.168.1.2", "network_prefix": 24},
        ],
        "ipv6": [],
    },
    {
        "name": "eth1",
        "index": 2,
        "enabled": True,
        "auto": False,
        "default": False,
        "ipv4": [{"address": "10.0.0.7", "network_prefix": 8}],
        "ipv6": [],
    },
    {
        "name": "eth2",
        "index": 3,
        "enabled": False,
        "auto": False,
        "default": False,
        "ipv4": [{"address": "172.16.0.5", "network_prefix": 16}],
        "ipv6": [],
    },
]

EXPECTED_LISTENING_ADDRESSES = ["10.0.0.7/8", "192.168.1.2/24"]

DISABLED_NETWORK_ADAPTERS: list[Adapter] = [
    {
        "name": "eth0",
        "index": 1,
        "enabled": False,
        "auto": False,
        "default": False,
        "ipv4": [{"address": "192.168.1.2", "network_prefix": 24}],
        "ipv6": [],
    },
]


@pytest.fixture(name="mock_network_adapters")
def fixture_mock_network_adapters() -> Generator[None]:
    """Mock a host with two enabled adapters and one disabled adapter."""
    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=NETWORK_ADAPTERS,
    ):
        yield


def set_mocked_devices(mock_govee_api: AsyncMock, devices: list[GoveeDevice]) -> None:
    """Update a mocked device."""
    devices_dict = {device.fingerprint: device for device in devices}
    devices_list = list(devices_dict.values())
    mock_govee_api._registry._discovered_devices = devices_dict

    type(mock_govee_api).devices = PropertyMock(return_value=devices_list)

    mock_govee_api.get_device_by_ip.side_effect = lambda ip: next(
        (device for device in mock_govee_api.devices if device.ip == ip), None
    )

    mock_govee_api.get_device_by_sku.side_effect = lambda sku: next(
        (device for device in mock_govee_api.devices if device.sku == sku), None
    )

    mock_govee_api.get_device_by_fingerprint.side_effect = lambda fingerprint: next(
        (
            device
            for device in mock_govee_api.devices
            if device.fingerprint == fingerprint
        ),
        None,
    )

    # The removal listener drops devices and the reconcile listener then reads
    # the remaining ones back, so this has to mutate the same lists rather than
    # only record the call.
    def _remove_device(device: str | GoveeDevice) -> None:
        fingerprint = device.fingerprint if isinstance(device, GoveeDevice) else device
        if removed := devices_dict.pop(fingerprint, None):
            devices_list.remove(removed)

    mock_govee_api.remove_device = MagicMock(side_effect=_remove_device)


@pytest.fixture(name="mock_govee_api")
def fixture_mock_govee_api() -> Generator[AsyncMock]:
    """Set up Govee Local API fixture."""

    mock_registry = MagicMock(spec=DeviceRegistry)
    mock_registry._discovered_devices = {}

    mock_api = AsyncMock(spec=GoveeController)
    mock_api._registry = mock_registry

    mock_api.start = AsyncMock()
    mock_api.cleanup = MagicMock(return_value=asyncio.Event())
    mock_api.cleanup.return_value.set()
    mock_api.turn_on_off = AsyncMock()
    mock_api.set_brightness = AsyncMock()
    mock_api.set_color = AsyncMock()
    mock_api.set_scene = AsyncMock()
    mock_api._async_update_data = AsyncMock()
    mock_api.get_device_by_ip = MagicMock()
    mock_api.get_device_by_sku = MagicMock()
    mock_api.get_device_by_fingerprint = MagicMock()

    # The reconcile listener reads and mutates the queue, so back it with a
    # real set rather than a bare mock attribute.
    discovery_queue: set[str] = set()

    def _add_to_queue(ip: str) -> bool:
        discovery_queue.add(ip)
        return True

    mock_api.add_device_to_discovery_queue = MagicMock(side_effect=_add_to_queue)

    # Like the library, dequeuing an address also forgets a manual lamp cached
    # there.
    def _remove_from_queue(ip: str) -> bool:
        if ip not in discovery_queue:
            return False
        discovery_queue.discard(ip)
        device = mock_api.get_device_by_ip(ip)
        if isinstance(device, GoveeDevice) and device.is_manual:
            mock_api._registry._discovered_devices.pop(device.fingerprint, None)
            mock_api.devices.remove(device)
        return True

    mock_api.remove_device_from_discovery_queue = MagicMock(
        side_effect=_remove_from_queue
    )
    type(mock_api).discovery_queue = PropertyMock(side_effect=lambda: discovery_queue)

    type(mock_api).devices = PropertyMock(return_value=[])

    # The library strips the mask off the address it stores, and keeps the
    # parsed network in a separate index-aligned list.
    mock_api.listening_addresses = ["10.0.0.7", "192.168.1.2"]
    mock_api.networks = [IPv4Network("10.0.0.0/8"), IPv4Network("192.168.1.0/24")]
    mock_api.bind_failures = []
    mock_api.protocols = [MagicMock()]
    mock_api.rebind_failed = AsyncMock(return_value=[])

    with (
        patch(
            "homeassistant.components.govee_light_local.coordinator.GoveeController",
            return_value=mock_api,
        ) as mock_controller,
        patch(
            "homeassistant.components.govee_light_local.config_flow.GoveeController",
            return_value=mock_api,
        ),
    ):
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


DEFAULT_CAPABILITIES: GoveeLightCapabilities = GoveeLightCapabilities(
    features=COMMON_FEATURES, segments=[], scenes={}
)

SCENE_CAPABILITIES: GoveeLightCapabilities = GoveeLightCapabilities(
    features=COMMON_FEATURES | GoveeLightFeatures.SCENES,
    segments=[],
    scenes=SCENE_CODES,
)


async def setup_light(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    capabilities: GoveeLightCapabilities = DEFAULT_CAPABILITIES,
    *,
    ip: str = "192.168.1.100",
    fingerprint: str = "asdawdqwdqwd",
    sku: str = "H615A",
) -> tuple[MockConfigEntry, GoveeDevice]:
    """Set up a single mocked Govee light device and return its entry and device.

    The returned tuple lets tests that need to mutate the device after setup
    (e.g. ``device.update(...)`` in availability tests) access the underlying
    ``GoveeDevice`` directly. Tests that only need the entry or neither can
    discard the unused half with ``_``.
    """
    device = GoveeDevice(
        controller=mock_govee_api,
        ip=ip,
        fingerprint=fingerprint,
        sku=sku,
        capabilities=capabilities,
    )
    set_mocked_devices(mock_govee_api, [device])

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry, device
