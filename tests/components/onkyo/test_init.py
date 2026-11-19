"""Test Onkyo component setup process."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

from aioonkyo import Instruction, Receiver, ReceiverInfo, Status, Zone, command, query
from aioonkyo.protocol import OnkyoConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import (
    DISCONNECT,
    RECEIVER_INFO,
    mock_discovery,
    receive_messages,
    setup_integration,
)


@pytest.mark.usefixtures("mock_receiver")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("receiver_infos", "translation_key"),
    [
        pytest.param(None, "interview_error", id="interview_error"),
        pytest.param([], "interview_timeout", id="interview_timeout"),
    ],
)
async def test_initialization_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    receiver_infos: list[ReceiverInfo] | None,
    translation_key: str,
) -> None:
    """Test initialization failure."""
    with mock_discovery(receiver_infos):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders == {
        "host": RECEIVER_INFO.host
    }


async def test_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
) -> None:
    """Test connection failure."""
    mock_connect.side_effect = OSError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "host": RECEIVER_INFO.host
    }


@pytest.mark.usefixtures("mock_receiver")
async def test_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
    read_queue: asyncio.Queue[Status | None],
) -> None:
    """Test reconnect."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    manager = mock_config_entry.runtime_data.manager
    assert manager.connected is True

    async def disconnect_assert() -> None:
        assert manager.connected is False

    manager.callbacks.disconnect.append(disconnect_assert)

    mock_connect.reset_mock()

    assert mock_connect.call_count == 0

    await receive_messages(read_queue, DISCONNECT)

    assert mock_connect.call_count == 1


async def test_reconnect_after_failed_power_query(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
    mock_receiver: AsyncMock,
    writes: list[Instruction],
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recover when the receiver disconnects during the initial zone query."""
    disconnected_receiver = AsyncMock(spec=Receiver)
    disconnected_receiver.write.side_effect = OnkyoConnectionError("Connection reset")
    mock_connect.side_effect = [
        disconnected_receiver,
        disconnected_receiver,
        mock_receiver,
    ]

    await setup_integration(hass, mock_config_entry)
    disconnected_receiver.write.assert_awaited_once_with(query.Power(Zone.MAIN))
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Consecutive failed queries back off for one second, then two.
    for attempts in (2, 2, 3):
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_connect.await_count == attempts

    # Failed retries log one outage, not one per attempt.
    assert caplog.text.count("Disconnected:") == 1
    assert caplog.text.count("Reconnected:") == 1

    entity_id = "media_player.tx_nr7100"
    assert hass.states.get(entity_id).state == STATE_ON
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert writes[-1] == command.Power(Zone.MAIN, command.Power.Param.STANDBY)
