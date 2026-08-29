"""Tests for the Haus-Bus gateway."""

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from tests.common import MockConfigEntry

from homeassistant.components.hausbus.const import NEW_CHANNEL_ADDED
from homeassistant.components.hausbus.gateway import (
    HausbusGateway,
    _home_server_refs,
    async_acquire_home_server,
    async_release_home_server,
)


@patch("homeassistant.components.hausbus.gateway.async_dispatcher_send")
def test_register_channel_ignores_duplicates(
    mock_dispatcher: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_home_server: MagicMock,
) -> None:
    """Test duplicate channel discovery is ignored."""

    gateway = HausbusGateway(
        hass,
        mock_config_entry,
        mock_home_server,
    )

    gateway._platform_ready = True

    channel = MagicMock()
    channel.getObjectId.return_value = 123

    device_info = DeviceInfo(
        identifiers={("hausbus", "1")},
    )

    gateway._register_channel(channel, device_info)
    gateway._register_channel(channel, device_info)

    mock_dispatcher.assert_called_once_with(
        hass,
        NEW_CHANNEL_ADDED,
        channel,
        device_info,
    )

    assert gateway.registered_channels == {123}


@patch("homeassistant.components.hausbus.gateway.async_dispatcher_send")
async def test_buffered_channels_flushed_after_platform_ready(
    mock_dispatcher: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_home_server: MagicMock,
) -> None:
    """Test channels discovered before platform setup are buffered."""

    gateway = HausbusGateway(
        hass,
        mock_config_entry,
        mock_home_server,
    )

    channel = MagicMock()
    channel.getObjectId.return_value = 123

    device_info = DeviceInfo(
        identifiers={("hausbus", "1")},
    )

    gateway._register_channel(channel, device_info)

    assert gateway._platform_ready is False
    assert len(gateway._pending_channels) == 1

    mock_dispatcher.assert_not_called()

    await gateway.async_flush_pending_channels()

    assert gateway._platform_ready is True
    assert gateway._pending_channels == []

    mock_dispatcher.assert_called_once_with(
        hass,
        NEW_CHANNEL_ADDED,
        channel,
        device_info,
    )


async def test_home_server_reference_counting(
    hass: HomeAssistant,
    mock_home_server: MagicMock,
) -> None:
    """Test HomeServer reference counting and shutdown."""

    home_server_1 = await async_acquire_home_server(hass)
    home_server_2 = await async_acquire_home_server(hass)

    assert home_server_1 is home_server_2
    assert _home_server_refs[home_server_1] == 2

    await async_release_home_server(hass, home_server_1)

    assert _home_server_refs[home_server_1] == 1
    mock_home_server.shutdown.assert_not_called()

    await async_release_home_server(hass, home_server_2)

    mock_home_server.shutdown.assert_called_once()
    assert home_server_1 not in _home_server_refs