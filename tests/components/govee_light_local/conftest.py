"""Tests configuration for Govee Local API."""

import asyncio
from collections.abc import Generator
from ipaddress import IPv4Network
from unittest.mock import AsyncMock, MagicMock, patch

from govee_local_api import GoveeDevice, GoveeLightCapabilities, GoveeLightFeatures
from govee_local_api.light_capabilities import COMMON_FEATURES, SCENE_CODES
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.components.govee_light_local.coordinator import GoveeController
from homeassistant.components.network import Adapter
from homeassistant.const import CONF_IP_ADDRESS
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
    mock_api.send_discovery_message = MagicMock(
        side_effect=lambda: [
            scan_reply(mock_api, device) for device in mock_api.answering_devices
        ]
    )

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_api,
    ) as mock_controller:
        yield mock_controller.return_value


def scan_reply(mock_govee_api: AsyncMock, device: GoveeDevice) -> bool:
    """Deliver a lamp's scan reply the way the library does.

    The library only starts tracking a lamp the integration accepts.
    """
    discovered_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    is_new = device not in mock_govee_api.devices
    device.update_lastseen()
    accepted: bool = discovered_callback(device, is_new)
    if accepted and is_new:
        mock_govee_api.devices.append(device)
    return accepted


def answer_scans(mock_govee_api: AsyncMock, *devices: GoveeDevice) -> None:
    """Make the lamps answer every scan from now on."""
    mock_govee_api.answering_devices.extend(devices)


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


def create_device(
    mock_govee_api: AsyncMock,
    capabilities: GoveeLightCapabilities = DEFAULT_CAPABILITIES,
    *,
    ip: str = "192.168.1.100",
    fingerprint: str = "asdawdqwdqwd",
    sku: str = "H615A",
) -> GoveeDevice:
    """Create a Govee light device."""
    return GoveeDevice(
        controller=mock_govee_api,
        ip=ip,
        fingerprint=fingerprint,
        sku=sku,
        capabilities=capabilities,
    )


def create_entry(hass: HomeAssistant, device: GoveeDevice) -> MockConfigEntry:
    """Add the config entry of a single lamp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title=device.sku,
        unique_id=device.fingerprint,
        data={CONF_IP_ADDRESS: device.ip},
    )
    entry.add_to_hass(hass)
    return entry


def create_legacy_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add the single config entry that predates one entry per lamp."""
    entry = MockConfigEntry(domain=DOMAIN, title="Govee light local", unique_id=DOMAIN)
    entry.add_to_hass(hass)
    return entry


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
    device = create_device(
        mock_govee_api, capabilities, ip=ip, fingerprint=fingerprint, sku=sku
    )
    answer_scans(mock_govee_api, device)
    entry = create_entry(hass, device)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry, device
