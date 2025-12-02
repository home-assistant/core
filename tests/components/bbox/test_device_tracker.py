"""Define tests for the Bbox device tracker."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aiobbox.models import (
    DeviceInfo,
    EthernetInfo,
    Host,
    ParentalControl,
    PingInfo,
    PLCInfo,
    ScanInfo,
    WirelessInfo,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bbox.const import SCAN_INTERVAL
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import DEVICE_1_HOSTNAME, DEVICE_1_MAC, DEVICE_2_HOSTNAME, DEVICE_2_MAC

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.bbox.PLATFORMS", [Platform.DEVICE_TRACKER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_states(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device tracker states."""
    await setup_integration(hass, mock_config_entry)

    device_1_tracker = f"device_tracker.{DEVICE_1_HOSTNAME}"
    device_2_tracker = f"device_tracker.{DEVICE_2_HOSTNAME}"

    # Both devices should be home (active=True)
    assert (state := hass.states.get(device_1_tracker))
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == DEVICE_1_MAC
    assert state.attributes["ip"] == "192.168.1.10"

    assert (state := hass.states.get(device_2_tracker))
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == DEVICE_2_MAC
    assert state.attributes["ip"] == "192.168.1.11"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_disconnection(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device disconnection."""
    await setup_integration(hass, mock_config_entry)

    device_1_tracker = f"device_tracker.{DEVICE_1_HOSTNAME}"

    # Initially home
    assert (state := hass.states.get(device_1_tracker))
    assert state.state == STATE_HOME

    # Simulate device disconnection
    mock_bbox_api.get_hosts.return_value[0].active = False

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Device should be not_home
    assert (state := hass.states.get(device_1_tracker))
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_reconnection(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device reconnection."""
    await setup_integration(hass, mock_config_entry)

    device_1_tracker = f"device_tracker.{DEVICE_1_HOSTNAME}"

    # Simulate device disconnection
    mock_bbox_api.get_hosts.return_value[0].active = False

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Device should be not_home
    assert (state := hass.states.get(device_1_tracker))
    assert state.state == STATE_NOT_HOME

    # Simulate device reconnection
    mock_bbox_api.get_hosts.return_value[0].active = True

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Device should be home again
    assert (state := hass.states.get(device_1_tracker))
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_new_device_discovery(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new device discovery."""
    await setup_integration(hass, mock_config_entry)

    # Initially 2 devices
    device_1_tracker = f"device_tracker.{DEVICE_1_HOSTNAME}"
    device_2_tracker = f"device_tracker.{DEVICE_2_HOSTNAME}"

    assert hass.states.get(device_1_tracker)
    assert hass.states.get(device_2_tracker)

    new_device = Host(
        id=3,
        active=True,
        devicetype="tablet",
        duid=None,
        guest=False,
        hostname="NewTablet",
        ipaddress="192.168.1.12",
        lease=86400,
        link="wifi_5",
        macaddress="33:44:55:66:77:88",
        type="dhcp",
        firstseen=datetime.now(UTC),
        lastseen=900,
        serialNumber=None,
        ip6address=None,
        ethernet=EthernetInfo(
            physicalport=0,
            logicalport=0,
            speed=0,
            mode="",
        ),
        wireless=WirelessInfo(
            wexindex=0,
            static=False,
            band="5",
            txUsage=0,
            rxUsage=0,
            estimatedRate=433,
            rssi0=-55,
            mcs=8,
            rate=433,
        ),
        wirelessByBand=[],
        plc=PLCInfo(
            rxphyrate=0,
            txphyrate=0,
            associateddevice=0,
            interface=0,
            ethernetspeed=0,
        ),
        informations=DeviceInfo(  # codespell:ignore informations
            type="tablet",
            manufacturer="Apple",
            model="iPad",
            icon="tablet",
            operatingSystem="iOS",
            version="17",
        ),
        parentalcontrol=ParentalControl(
            enable=False,
            status="allowed",
            statusRemaining=0,
            statusUntil=None,
        ),
        ping=PingInfo(average=3),
        scan=ScanInfo(services=[]),
    )

    mock_bbox_api.get_hosts.return_value.append(new_device)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # New device should be discovered
    new_device_tracker = "device_tracker.newtablet"
    assert (state := hass.states.get(new_device_tracker))
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "33:44:55:66:77:88"
    assert state.attributes["ip"] == "192.168.1.12"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_without_hostname(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device without hostname uses MAC address."""
    # Set device 1 to have no hostname before integration setup
    mock_bbox_api.get_hosts.return_value[0].hostname = None

    await setup_integration(hass, mock_config_entry)

    # Device should use device model as entity ID when hostname is None
    device_tracker = "device_tracker.pc"
    assert (state := hass.states.get(device_tracker))
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == DEVICE_1_MAC


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_guest_device(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test guest device tracking."""
    await setup_integration(hass, mock_config_entry)

    # Modify device 1 to be a guest device
    mock_bbox_api.get_hosts.return_value[0].guest = True

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Guest device should still be tracked
    device_tracker = f"device_tracker.{DEVICE_1_HOSTNAME}"
    assert (state := hass.states.get(device_tracker))
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == DEVICE_1_MAC
