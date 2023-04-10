"""Tests for the Sonos config flow."""
import logging
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import sonos, zeroconf
from homeassistant.components.sonos import SonosDiscoveryManager
from homeassistant.components.sonos.const import DATA_SONOS_DISCOVERY_MANAGER
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
    ), patch("homeassistant.components.sonos.async_call_later"), patch(
        "homeassistant.components.sonos.async_dispatcher_send"
    ), patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_async_add_executor_job:
        _should_raise = True

        def executor_side_effect(_, arg):
            if arg == "10.10.10.10":
                # for socket.gethostbyaddr which is mocked by an autoused fixture
                return arg
            nonlocal _should_raise
            if _should_raise:
                raise OSError()
            return []

        mock_async_add_executor_job.side_effect = executor_side_effect

        # First call fails, it should be logged as a WARNING message
        _should_raise = True
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "WARNING"
        assert "Could not get visible Sonos devices from" in record.message

        # Second call fails again, it should be logged as a DEBUG message
        _should_raise = True
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "DEBUG"
        assert "Could not get visible Sonos devices from" in record.message

        # Third call succeeds, it should log an info message
        _should_raise = False
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "INFO"
        assert "Connection restablished to Sonos device" in record.message

        # Fourth call succeeds again, no need to log
        _should_raise = False
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 0

        # Fifth call fail again again, should be logged as a WARNING message
        _should_raise = True
        caplog.clear()
        await manager.async_poll_manual_hosts()
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "WARNING"
        assert "Could not get visible Sonos devices from" in record.message
