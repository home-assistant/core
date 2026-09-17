"""Test Onkyo component setup process."""

import asyncio
from unittest.mock import AsyncMock

from aioonkyo import ReceiverInfo, Status
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.onkyo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import RECEIVER_INFO, mock_discovery, setup_integration

from tests.common import MockConfigEntry


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


@pytest.mark.usefixtures("mock_receiver")
async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the receiver device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, RECEIVER_INFO.identifier), mock_config_entry.entry_id
    )
    assert device == snapshot


@pytest.mark.usefixtures("mock_receiver")
@pytest.mark.parametrize("initial_messages", [[]])
async def test_device_without_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the device is created before the receiver reports any of its zones."""
    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, RECEIVER_INFO.identifier), mock_config_entry.entry_id
    )


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

    # Simulate a disconnect
    read_queue.put_nowait(None)
    await asyncio.sleep(0)

    assert mock_connect.call_count == 1
