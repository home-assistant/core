"""Tests for the Sonos config flow."""
import asyncio
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import sonos, zeroconf
from homeassistant.components.sonos import SonosDiscoveryManager
from homeassistant.components.sonos.const import DATA_SONOS_DISCOVERY_MANAGER
from homeassistant.components.sonos.exception import SonosUpdateError
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


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


async def patch_gethostbyname(host: str) -> str:
    """Mock to return host name as ip address for testing."""
    return host


async def test_async_poll_manual_hosts_ping_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a failure to ping device is handled properly."""
    await async_setup_component(
        hass,
        sonos.DOMAIN,
        {"sonos": {"media_player": {"interface_addr": "127.0.0.1"}}},
    )
    await hass.async_block_till_done()
    manager: SonosDiscoveryManager = hass.data[DATA_SONOS_DISCOVERY_MANAGER]
    with patch.object(manager, "_async_gethostbyname", side_effect=patch_gethostbyname):
        manager.hosts.add("10.10.10.10")

        with caplog.at_level(logging.DEBUG), patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ), patch.object(
            hass, "async_add_executor_job", new=AsyncMock()
        ) as mock_async_add_executor_job:
            mock_async_add_executor_job.return_value = []
            caplog.clear()

            mock_discovery_message.side_effect = asyncio.TimeoutError("TimeoutError")
            await manager.async_poll_manual_hosts()
            assert len(caplog.messages) == 1
            record = caplog.records[0]
            assert record.levelname == "WARNING"
            assert "Discovery message failed" in record.message
            assert "TimeoutError" in record.message
            mock_async_call_later.assert_called_once()


async def test_async_poll_manual_hosts(hass: HomeAssistant) -> None:
    """Tests the logic and execution branches for the function."""
    await async_setup_component(
        hass,
        sonos.DOMAIN,
        {"sonos": {"media_player": {"interface_addr": "127.0.0.1"}}},
    )
    await hass.async_block_till_done()
    manager: SonosDiscoveryManager = hass.data[DATA_SONOS_DISCOVERY_MANAGER]

    with patch.object(manager, "_async_gethostbyname", side_effect=patch_gethostbyname):
        manager.hosts.add("10.10.10.1")
        manager.hosts.add("10.10.10.2")

        # Test 1 first device fails, second device successful, speakers do not exist
        with patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ), patch.object(
            hass,
            "async_add_executor_job",
            new=AsyncMock(),
        ) as mock_async_add_executor_job:
            mock_async_add_executor_job.side_effect = [OSError(), []]
            await manager.async_poll_manual_hosts()
            assert mock_async_add_executor_job.call_count == 2
            assert mock_discovery_message.call_count == 1
            assert mock_async_call_later.call_count == 1

        # Test 2 first device successful, second device fails, speakers do not exist
        with patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ), patch.object(
            hass, "async_add_executor_job", new=AsyncMock()
        ) as mock_async_add_executor_job:
            mock_async_add_executor_job.side_effect = [[], OSError()]
            await manager.async_poll_manual_hosts()
            assert mock_async_add_executor_job.call_count == 2
            assert mock_discovery_message.call_count == 1
            assert mock_async_call_later.call_count == 1

        # Test 3 both devices fail, speakers do not exist
        with patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ), patch.object(
            hass, "async_add_executor_job", new=AsyncMock()
        ) as mock_async_add_executor_job:
            mock_async_add_executor_job.side_effect = OSError()
            await manager.async_poll_manual_hosts()
            assert mock_async_add_executor_job.call_count == 2
            assert mock_discovery_message.call_count == 0
            assert mock_async_call_later.call_count == 1

        # Test 4 both devices are successful, speakers do not exist
        with patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ), patch.object(
            hass, "async_add_executor_job", new=AsyncMock()
        ) as mock_async_add_executor_job:
            mock_async_add_executor_job.return_value = []
            await manager.async_poll_manual_hosts()
            assert mock_async_add_executor_job.call_count == 2
            assert mock_discovery_message.call_count == 2
            assert mock_async_call_later.call_count == 1

        # Test 5 both succeed, speakers exist and unavailable, ping succeeds
        with patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ) as mock_async_dispatcher_send, patch.object(
            hass, "async_add_executor_job", new=AsyncMock()
        ) as mock_async_add_executor_job:
            speaker_1_mock = Mock()
            speaker_1_mock.soco.ip_address = "10.10.10.1"
            speaker_1_mock.available = False
            speaker_2_mock = Mock()
            speaker_2_mock.soco.ip_address = "10.10.10.2"
            speaker_2_mock.available = False
            manager.data.discovered = {
                "10.10.10.1": speaker_1_mock,
                "10.10.10.2": speaker_2_mock,
            }
            mock_async_add_executor_job.return_value = []
            await manager.async_poll_manual_hosts()
            assert mock_async_add_executor_job.call_count == 4
            assert mock_async_dispatcher_send.call_count == 2
            assert mock_discovery_message.call_count == 0
            assert mock_async_call_later.call_count == 1
            manager.data.discovered = {}

        # Test 6 both succeed, speakers exist and unavailable, pings fail
        with patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ) as mock_async_dispatcher_send, patch.object(
            hass, "async_add_executor_job", new=AsyncMock()
        ) as mock_async_add_executor_job:
            speaker_1_mock = Mock()
            speaker_1_mock.soco.ip_address = "10.10.10.1"
            speaker_1_mock.available = False
            speaker_2_mock = Mock()
            speaker_2_mock.soco.ip_address = "10.10.10.2"
            speaker_2_mock.available = False
            manager.data.discovered = {
                "10.10.10.1": speaker_1_mock,
                "10.10.10.2": speaker_2_mock,
            }
            mock_async_add_executor_job.side_effect = [
                [],
                [],
                SonosUpdateError(),
                SonosUpdateError(),
            ]
            await manager.async_poll_manual_hosts()
            assert mock_async_add_executor_job.call_count == 4
            assert mock_async_dispatcher_send.call_count == 0
            assert mock_discovery_message.call_count == 0
            assert mock_async_call_later.call_count == 1
            manager.data.discovered = {}

        # Test 7 both succeed, speaker do not exist, new host found in visible zones
        with patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ) as mock_async_dispatcher_send, patch.object(
            hass, "async_add_executor_job", new=AsyncMock()
        ) as mock_async_add_executor_job:
            visible_zone_3_mock = Mock()
            visible_zone_3_mock.ip_address = "10.10.10.3"
            visible_zone_4_mock = Mock()
            visible_zone_4_mock.ip_address = "10.10.10.4"
            visible_zone_5_mock = Mock()
            visible_zone_5_mock.ip_address = "10.10.10.5"
            mock_async_add_executor_job.side_effect = [
                [visible_zone_3_mock],
                [visible_zone_4_mock, visible_zone_5_mock],
            ]
            await manager.async_poll_manual_hosts()
            assert len(manager.hosts) == 5
            assert "10.10.10.3" in manager.hosts
            assert "10.10.10.4" in manager.hosts
            assert "10.10.10.5" in manager.hosts
            assert mock_async_add_executor_job.call_count == 2
            assert mock_async_dispatcher_send.call_count == 0
            assert mock_discovery_message.call_count == 5
            assert mock_async_call_later.call_count == 1
            manager.data.discovered = {}
            manager.hosts.discard("10.10.10.3")
            manager.hosts.discard("10.10.10.4")
            manager.hosts.discard("10.10.10.5")

        def device_is_invisible(ip_addr: str) -> bool:
            if ip_addr == "10.10.10.1":
                return True
            return False

        # Test 8 both succeed, speakers do not exist, first one is invisible
        with patch.object(
            manager, "_async_handle_discovery_message", new=AsyncMock()
        ) as mock_discovery_message, patch(
            "homeassistant.components.sonos.async_call_later"
        ) as mock_async_call_later, patch(
            "homeassistant.components.sonos.async_dispatcher_send"
        ) as mock_async_dispatcher_send, patch.object(
            hass, "async_add_executor_job", new=AsyncMock()
        ) as mock_async_add_executor_job, patch.object(
            manager, "is_device_invisible"
        ) as mock_is_device_invisible:
            mock_async_add_executor_job.return_value = []
            mock_is_device_invisible.side_effect = device_is_invisible
            await manager.async_poll_manual_hosts()
            assert len(manager.hosts) == 1
            assert "10.10.10.2" in manager.hosts
            assert mock_async_add_executor_job.call_count == 2
            assert mock_async_dispatcher_send.call_count == 0
            assert mock_discovery_message.call_count == 1
            assert mock_async_call_later.call_count == 1
            manager.data.discovered = {}
