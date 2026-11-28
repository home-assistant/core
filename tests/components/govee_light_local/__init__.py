"""Tests for the Govee Light local integration."""

import asyncio
from unittest.mock import AsyncMock

from govee_local_api import GoveeDevice, GoveeLightCapabilities, GoveeLightFeatures
from govee_local_api.light_capabilities import COMMON_FEATURES, SCENE_CODES
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.components.network import Adapter
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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

DEFAULT_CAPABILITIES: GoveeLightCapabilities = GoveeLightCapabilities(
    features=COMMON_FEATURES, segments=[], scenes={}
)

SCENE_CAPABILITIES: GoveeLightCapabilities = GoveeLightCapabilities(
    features=COMMON_FEATURES | GoveeLightFeatures.SCENES,
    segments=[],
    scenes=SCENE_CODES,
)


def scan_reply(mock_govee_api: AsyncMock, device: GoveeDevice) -> bool:
    """Deliver a lamp's scan reply the way the library does.

    The library only starts tracking a lamp the integration accepts.
    """
    discovered_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    is_new = device not in mock_govee_api.devices
    device.update_lastseen()
    accepted: bool = discovered_callback(device, is_new)
    if accepted and is_new:
        # A lamp found at a queued address keeps being scanned at its address.
        device.is_manual = device.ip in mock_govee_api.discovery_queue
        mock_govee_api.discovery_queue.discard(device.ip)
        mock_govee_api.devices.append(device)
    return accepted


async def wait_for_scan(
    hass: HomeAssistant, result: ConfigFlowResult
) -> ConfigFlowResult:
    """Return the outcome of the user flow once its scan is no longer in progress."""
    # async_block_till_done does not wait for a task its own timeout is cancelling.
    while result["type"] is FlowResultType.SHOW_PROGRESS:
        await asyncio.sleep(0)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    return result


async def start_user_flow(hass: HomeAssistant, next_step_id: str) -> ConfigFlowResult:
    """Start the user flow and pick an option of its menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": next_step_id}
    )


async def start_user_scan(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the user flow, pick searching the network and wait for its outcome."""
    return await wait_for_scan(hass, await start_user_flow(hass, "scan"))


async def start_user_manual(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the user flow and pick entering the address of a lamp."""
    return await start_user_flow(hass, "manual")


def answer_probes(mock_govee_api: AsyncMock, *devices: GoveeDevice) -> None:
    """Make the lamps answer only the scans sent to their own address."""
    mock_govee_api.probe_only_devices.extend(devices)


def answer_scans(mock_govee_api: AsyncMock, *devices: GoveeDevice) -> None:
    """Make the lamps answer every scan from now on."""
    mock_govee_api.answering_devices.extend(devices)


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
