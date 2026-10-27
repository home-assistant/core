"""Tests for the System Bridge sensor platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.models.fixtures.modules.cpu import FIXTURE_CPU
from systembridgeconnector.models.fixtures.modules.disks import FIXTURE_DISKS
from systembridgeconnector.models.fixtures.modules.memory import FIXTURE_MEMORY
from systembridgeconnector.models.fixtures.modules.networks import FIXTURE_NETWORKS
from systembridgeconnector.models.modules import Module
from systembridgeconnector.models.modules.disks import Disk, DiskIOCounters, Disks
from systembridgeconnector.models.modules.networks import (
    Network,
    NetworkIO,
    Networks,
    NetworkStats,
    NetworkWifi,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.mark.usefixtures(
    "mock_version", "mock_websocket_client", "entity_registry_enabled_by_default"
)
@pytest.mark.freeze_time("1970-01-01 00:00:00")
async def test_sensor_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the sensor platform."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_version")
async def test_sensor_memory_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test memory sensors are unknown when there is no memory data."""
    mock_websocket_client.get_data.return_value = replace(
        mock_websocket_client.get_data.return_value, memory=None
    )
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.hostname_memory_used")
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_version")
async def test_sensor_load_average_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test load average sensors are not added when they are not reported."""
    mock_websocket_client.get_data.return_value = replace(
        mock_websocket_client.get_data.return_value,
        cpu=replace(
            FIXTURE_CPU, load_average=None, load_average_5=None, load_average_15=None
        ),
    )
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.hostname_load") is not None
    assert hass.states.get("sensor.hostname_load_average_1_min") is None


@pytest.mark.usefixtures("mock_version")
async def test_sensor_memory_free_uses_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test free memory counts reclaimable cache, not only unused memory."""
    mock_websocket_client.get_data.return_value = replace(
        mock_websocket_client.get_data.return_value,
        memory=replace(
            FIXTURE_MEMORY,
            virtual=replace(
                FIXTURE_MEMORY.virtual,
                free=1_500_000_000,
                available=73_000_000_000,
            ),
        ),
    )
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("sensor.hostname_memory_free"))
    assert state.state == "73.0"


@pytest.mark.usefixtures("mock_version", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "networks",
    [
        pytest.param(None, id="no_network_data"),
        pytest.param(
            replace(
                FIXTURE_NETWORKS,
                io=None,
                networks=[Network(name="name", stats=NetworkStats(flags=["up"]))],
            ),
            id="no_io_or_wifi_data",
        ),
    ],
)
async def test_sensor_network_data_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    networks: Networks | None,
) -> None:
    """Test network sensors are unknown when their data goes missing."""
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await mock_config_entry.runtime_data.async_handle_module(Module.NETWORKS, networks)
    await hass.async_block_till_done()

    for entity_id in (
        "sensor.hostname_network_download_rate",
        "sensor.hostname_network_upload_rate",
        "sensor.hostname_name_download_rate",
        "sensor.hostname_name_upload_rate",
        "sensor.hostname_name_ssid",
        "sensor.hostname_name_signal_strength",
        "sensor.hostname_name_link_rate",
    ):
        assert (state := hass.states.get(entity_id)), entity_id
        assert state.state == STATE_UNKNOWN, entity_id


@pytest.mark.usefixtures("mock_version", "entity_registry_enabled_by_default")
async def test_sensor_network_interface_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test sensors are added for interfaces that appear after setup."""
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.hostname_eth0_download_rate") is None

    networks = FIXTURE_NETWORKS.networks
    assert networks is not None
    await mock_config_entry.runtime_data.async_handle_module(
        Module.NETWORKS,
        replace(
            FIXTURE_NETWORKS,
            networks=[
                *networks,
                Network(
                    name="lo",
                    stats=NetworkStats(flags=["up", "loopback"]),
                    io=NetworkIO(bytes_recv_rate=1000.0),
                ),
                Network(
                    name="eth0",
                    stats=NetworkStats(flags=["up"]),
                    io=NetworkIO(bytes_recv_rate=125000.0),
                ),
            ],
        ),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.hostname_eth0_download_rate"))
    assert state.state == "1.0"
    assert hass.states.get("sensor.hostname_eth0_ssid") is None
    assert hass.states.get("sensor.hostname_lo_download_rate") is None


@pytest.mark.usefixtures("mock_version", "entity_registry_enabled_by_default")
async def test_sensor_network_interface_wifi_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test Wi-Fi sensors are added when a known interface gets Wi-Fi data."""
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    networks = FIXTURE_NETWORKS.networks
    assert networks is not None
    wlan1 = Network(
        name="wlan1",
        stats=NetworkStats(flags=["up"]),
        io=NetworkIO(bytes_recv_rate=125000.0),
    )
    coordinator = mock_config_entry.runtime_data

    await coordinator.async_handle_module(
        Module.NETWORKS, replace(FIXTURE_NETWORKS, networks=[*networks, wlan1])
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.hostname_wlan1_download_rate")
    assert hass.states.get("sensor.hostname_wlan1_ssid") is None

    await coordinator.async_handle_module(
        Module.NETWORKS,
        replace(
            FIXTURE_NETWORKS,
            networks=[*networks, replace(wlan1, wifi=NetworkWifi(ssid="Home"))],
        ),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.hostname_wlan1_ssid"))
    assert state.state == "Home"


@pytest.mark.usefixtures("mock_version", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "disks",
    [
        pytest.param(None, id="no_disk_data"),
        pytest.param(
            replace(
                FIXTURE_DISKS,
                io_counters=None,
                devices=[Disk(name="name", partitions=[])],
            ),
            id="no_io_data",
        ),
    ],
)
async def test_sensor_disk_data_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    disks: Disks | None,
) -> None:
    """Test disk sensors are unknown when their data goes missing."""
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await mock_config_entry.runtime_data.async_handle_module(Module.DISKS, disks)
    await hass.async_block_till_done()

    for entity_id in (
        "sensor.hostname_disk_read_rate",
        "sensor.hostname_disk_write_rate",
        "sensor.hostname_name_read_rate",
        "sensor.hostname_name_write_rate",
    ):
        assert (state := hass.states.get(entity_id)), entity_id
        assert state.state == STATE_UNKNOWN, entity_id


@pytest.mark.usefixtures("mock_version", "entity_registry_enabled_by_default")
async def test_sensor_disk_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test sensors are added for disks that appear after setup."""
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.hostname_dev_sdb1_read_rate") is None

    await mock_config_entry.runtime_data.async_handle_module(
        Module.DISKS,
        replace(
            FIXTURE_DISKS,
            devices=[
                *FIXTURE_DISKS.devices,
                Disk(name="/dev/sdc1", partitions=[]),
                Disk(
                    name="/dev/sdb1",
                    partitions=[],
                    io_counters=DiskIOCounters(
                        read_count=1,
                        write_count=1,
                        read_bytes=1,
                        write_bytes=1,
                        read_time=1,
                        write_time=1,
                        read_bytes_rate=2_000_000.0,
                    ),
                ),
            ],
        ),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.hostname_dev_sdb1_read_rate"))
    assert state.state == "2.0"
    assert hass.states.get("sensor.hostname_dev_sdc1_read_rate") is None
