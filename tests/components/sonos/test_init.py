"""Tests for the Sonos config flow."""
import asyncio
import logging
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import sonos, zeroconf
from homeassistant.components.sonos import SonosDiscoveryManager
from homeassistant.components.sonos.const import DATA_SONOS_DISCOVERY_MANAGER
from homeassistant.components.sonos.exception import SonosUpdateError
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MockSoco, SocoMockFactory


async def test_creating_entry_sets_up_media_player(
    hass: HomeAssistant, zeroconf_payload: zeroconf.ZeroconfServiceInfo
) -> None:
    """Test setting up Sonos loads the media player."""

    # Initiate a discovery to allow a user config flow
    await hass.config_entries.flow.async_init(
        sonos.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_payload,
    )

    with patch(
        "homeassistant.components.sonos.media_player.async_setup_entry",
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            sonos.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_sonos_creates_entry(hass: HomeAssistant) -> None:
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(
            hass,
            sonos.DOMAIN,
            {"sonos": {"media_player": {"interface_addr": "127.0.0.1"}}},
        )
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_sonos_not_creates_entry(hass: HomeAssistant) -> None:
    """Test that no config will not create an entry."""
    with patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(hass, sonos.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0


async def test_async_poll_manual_hosts_warnings(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that host warnings are not logged repeatedly."""
    await async_setup_component(
        hass,
        sonos.DOMAIN,
        {"sonos": {"media_player": {"interface_addr": "127.0.0.1"}}},
    )
    await hass.async_block_till_done()
    manager: SonosDiscoveryManager = hass.data[DATA_SONOS_DISCOVERY_MANAGER]
    manager.hosts.add("10.10.10.10")
    with caplog.at_level(logging.DEBUG), patch.object(
        manager, "_async_handle_discovery_message"
    ), patch(
        "homeassistant.components.sonos.async_call_later"
    ) as mock_async_call_later, patch(
        "homeassistant.components.sonos.async_dispatcher_send"
    ), patch(
        "homeassistant.components.sonos.sync_get_visible_zones",
        side_effect=[
            OSError(),
            OSError(),
            [],
            [],
            OSError(),
        ],
    ):
        # First call fails, it should be logged as a WARNING message
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "WARNING"
        assert "Could not get visible Sonos devices from" in record.message
        assert mock_async_call_later.call_count == 1

        # Second call fails again, it should be logged as a DEBUG message
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "DEBUG"
        assert "Could not get visible Sonos devices from" in record.message
        assert mock_async_call_later.call_count == 2

        # Third call succeeds, it should log an info message
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "INFO"
        assert "Connection reestablished to Sonos device" in record.message
        assert mock_async_call_later.call_count == 3

        # Fourth call succeeds again, no need to log
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 0
        assert mock_async_call_later.call_count == 4

        # Fifth call fail again again, should be logged as a WARNING message
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "WARNING"
        assert "Could not get visible Sonos devices from" in record.message
        assert mock_async_call_later.call_count == 5


class _MockSocoOsError(MockSoco):
    @property
    def visible_zones(self):
        raise OSError()


class _MockSocoVisibleZones(MockSoco):
    def set_visible_zones(self, visible_zones) -> None:
        """Set visible zones."""
        self.vz_return = visible_zones  # pylint: disable=attribute-defined-outside-init

    @property
    def visible_zones(self):
        return self.vz_return


@pytest.fixture(name="manager")
async def manager_fixture(hass: HomeAssistant):
    """Create fixture for SonosDiscovery Manager."""
    await async_setup_component(
        hass,
        sonos.DOMAIN,
        {"sonos": {"media_player": {"interface_addr": "127.0.0.1"}}},
    )
    await hass.async_block_till_done()
    manager: SonosDiscoveryManager = hass.data[DATA_SONOS_DISCOVERY_MANAGER]
    # Speed up unit tets
    with patch("homeassistant.components.sonos.ZGS_SUBSCRIPTION_TIMEOUT", 0):
        manager.hosts.add("10.10.10.2")
        manager.hosts.add("10.10.10.1")
        yield manager


async def test_async_poll_manual_hosts_1(
    hass: HomeAssistant, manager: SonosDiscoveryManager, soco_factory: SocoMockFactory
) -> None:
    """Tests the logic and execution branches for the function."""
    # Test: first device fails, second device successful, speakers do not exist
    soco_1 = soco_factory.cache_mock(_MockSocoOsError(), "10.10.10.1")
    soco_2 = soco_factory.get_mock("10.10.10.2")

    await manager.async_poll_manual_hosts()
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()

    assert soco_1.ip_address in manager.hosts_in_error
    assert soco_2.ip_address not in manager.hosts_in_error

    assert soco_1.uid not in manager.data.discovered
    assert manager.data.discovered[soco_2.uid].soco is soco_2
    # Verify task was schedule and then cancel it
    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None
    manager.data.discovered = {}


async def test_async_poll_manual_hosts_2(
    hass: HomeAssistant, manager: SonosDiscoveryManager, soco_factory: SocoMockFactory
) -> None:
    """Test first device success, second device fails, speakers do not exist."""
    soco_1 = soco_factory.get_mock("10.10.10.1")
    soco_2 = soco_factory.cache_mock(_MockSocoOsError(), "10.10.10.2")

    await manager.async_poll_manual_hosts()
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()

    assert soco_1.ip_address not in manager.hosts_in_error
    assert soco_2.ip_address in manager.hosts_in_error

    assert manager.data.discovered[soco_1.uid].soco is soco_1
    assert soco_2.uid not in manager.data.discovered

    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None
    manager.data.discovered = {}


async def test_async_poll_manual_hosts_3(
    hass: HomeAssistant, manager: SonosDiscoveryManager, soco_factory: SocoMockFactory
) -> None:
    """Test both devices fail, speakers do not exist."""
    soco_1 = soco_factory.cache_mock(_MockSocoOsError(), "10.10.10.1")
    soco_2 = soco_factory.cache_mock(_MockSocoOsError(), "10.10.10.2")

    await manager.async_poll_manual_hosts()
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()

    assert soco_1.ip_address in manager.hosts_in_error
    assert soco_2.ip_address in manager.hosts_in_error

    assert soco_1.uid not in manager.data.discovered
    assert soco_2.uid not in manager.data.discovered

    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None
    manager.data.discovered = {}


async def test_async_poll_manual_hosts_4(
    hass: HomeAssistant, manager: SonosDiscoveryManager, soco_factory: SocoMockFactory
) -> None:
    """Test both devices are successful, speakers do not exist."""
    soco_1 = soco_factory.get_mock("10.10.10.1")
    soco_2 = soco_factory.get_mock("10.10.10.2")

    await manager.async_poll_manual_hosts()
    await hass.async_block_till_done()

    assert soco_1.ip_address not in manager.hosts_in_error
    assert soco_2.ip_address not in manager.hosts_in_error

    assert manager.data.discovered[soco_1.uid].soco is soco_1
    assert manager.data.discovered[soco_2.uid].soco is soco_2

    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None
    manager.data.discovered = {}


async def test_async_poll_manual_hosts_5(
    hass: HomeAssistant, manager: SonosDiscoveryManager, soco_factory: SocoMockFactory
) -> None:
    """Test both succeed, speakers exist and unavailable, ping succeeds."""
    soco_1 = soco_factory.get_mock("10.10.10.1")
    soco_2 = soco_factory.get_mock("10.10.10.2")
    soco_1.renderingControl = Mock()
    soco_1.renderingControl.GetVolume = Mock()
    soco_2.renderingControl = Mock()
    soco_2.renderingControl.GetVolume = Mock()

    # Create the speakers
    await manager.async_poll_manual_hosts()
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()
    assert manager.data.discovered[soco_1.uid].soco is soco_1
    assert manager.data.discovered[soco_2.uid].soco is soco_2
    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None

    # Mark them unavailable and run again
    manager.data.discovered[soco_1.uid].available = False
    manager.data.discovered[soco_2.uid].available = False
    manager.data.discovered[soco_1.uid]._last_activity = 0
    manager.data.discovered[soco_1.uid]._resub_cooldown_expires_at = None
    manager.data.discovered[soco_2.uid]._last_activity = 0
    manager.data.discovered[soco_2.uid]._resub_cooldown_expires_at = None
    await manager.async_poll_manual_hosts()
    await hass.async_block_till_done()
    assert manager.data.discovered[soco_1.uid]._last_activity != 0
    assert manager.data.discovered[soco_2.uid]._last_activity != 0

    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None
    manager.data.discovered = {}


async def test_async_poll_manual_hosts_6(
    hass: HomeAssistant, manager: SonosDiscoveryManager, soco_factory: SocoMockFactory
) -> None:
    """Test both succeed, speakers exist and unavailable, pings fail."""
    soco_1 = soco_factory.get_mock("10.10.10.1")
    soco_2 = soco_factory.get_mock("10.10.10.2")

    # First setup the speakers
    await manager.async_poll_manual_hosts()
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()
    assert manager.data.discovered[soco_1.uid].soco is soco_1
    assert manager.data.discovered[soco_2.uid].soco is soco_2
    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None

    # Mark them unavailable and run again
    manager.data.discovered[soco_1.uid].available = False
    manager.data.discovered[soco_2.uid].available = False
    # Rendering Control Get Volume is what speaker ping calls.
    soco_1.renderingControl = Mock()
    soco_1.renderingControl.GetVolume = Mock()
    soco_1.renderingControl.GetVolume.side_effect = SonosUpdateError()
    soco_2.renderingControl = Mock()
    soco_2.renderingControl.GetVolume = Mock()
    soco_2.renderingControl.GetVolume.side_effect = SonosUpdateError()

    await manager.async_poll_manual_hosts()
    await hass.async_block_till_done()

    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None
    manager.data.discovered = {}


async def test_async_poll_manual_hosts_7(
    hass: HomeAssistant, manager: SonosDiscoveryManager, soco_factory: SocoMockFactory
) -> None:
    """Test both succeed, speaker do not exist, new hosts found in visible zones."""
    soco_3 = soco_factory.get_mock("10.10.10.3")
    soco_4 = soco_factory.get_mock("10.10.10.4")
    soco_5 = soco_factory.get_mock("10.10.10.5")
    soco_1 = soco_factory.cache_mock(_MockSocoVisibleZones(), "10.10.10.1")
    soco_1.set_visible_zones({soco_1, soco_3})
    soco_2 = soco_factory.cache_mock(_MockSocoVisibleZones(), "10.10.10.2")
    soco_2.set_visible_zones({soco_2, soco_4, soco_5})

    await manager.async_poll_manual_hosts()
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()

    assert len(manager.hosts) == 5
    assert "10.10.10.3" in manager.hosts
    assert "10.10.10.4" in manager.hosts
    assert "10.10.10.5" in manager.hosts

    assert manager.data.discovered[soco_1.uid].soco is soco_1
    assert manager.data.discovered[soco_2.uid].soco is soco_2
    assert manager.data.discovered[soco_3.uid].soco is soco_3
    assert manager.data.discovered[soco_4.uid].soco is soco_4
    assert manager.data.discovered[soco_5.uid].soco is soco_5

    assert manager.data.hosts_heartbeat
    manager.data.hosts_heartbeat()
    manager.data.hosts_heartbeat = None
    manager.data.discovered = {}


async def test_async_poll_manual_hosts_8(
    hass: HomeAssistant, manager: SonosDiscoveryManager, soco_factory: SocoMockFactory
) -> None:
    """Test both succeed, speakers do not exist, first one is invisible."""

    def device_is_invisible(ip_addr: str) -> bool:
        if ip_addr == "10.10.10.1":
            return True
        return False

    with patch.object(manager, "is_device_invisible") as mock_is_device_invisible:
        soco_1 = soco_factory.get_mock("10.10.10.1")
        soco_2 = soco_factory.get_mock("10.10.10.2")

        mock_is_device_invisible.side_effect = device_is_invisible
        await manager.async_poll_manual_hosts()
        await asyncio.sleep(0.5)
        await hass.async_block_till_done()

        assert "10.10.10.1" not in manager.hosts
        assert "10.10.10.2" in manager.hosts

        assert soco_1.uid not in manager.data.discovered
        assert manager.data.discovered[soco_2.uid].soco is soco_2

        assert manager.data.hosts_heartbeat
        manager.data.hosts_heartbeat()
        manager.data.hosts_heartbeat = None
        manager.data.discovered = {}
