"""Test the Anthem A/V Receivers config flow."""

import asyncio
from collections.abc import Callable
from unittest.mock import ANY, AsyncMock, patch

from anthemav.device_error import DeviceError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.anthemav.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_connection_create: AsyncMock,
    mock_anthemav: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test load and unload AnthemAv component."""
    # assert avr is created
    mock_connection_create.assert_called_with(
        host="1.1.1.1", port=14999, update_callback=ANY
    )
    assert init_integration.state is ConfigEntryState.LOADED

    # unload
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    # assert unload and avr is closed
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_anthemav.close.assert_called_once()


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00:00:00:00:00:01"), init_integration.entry_id
    )
    assert device_entry
    assert device_entry == snapshot

    zone_2_device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00:00:00:00:00:01_2"), init_integration.entry_id
    )
    assert zone_2_device_entry
    assert zone_2_device_entry.via_device_id == device_entry.id


@pytest.mark.parametrize("error", [OSError, DeviceError])
async def test_config_entry_not_ready_when_oserror(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, error: Exception
) -> None:
    """Test AnthemAV configuration entry not ready."""
    with patch(
        "anthemav.Connection.create",
        side_effect=error,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_when_connect_hangs(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails fast (instead of hanging) when the AVR never connects.

    anthemav.Connection.create() retries its initial connection internally
    and only returns once it succeeds, so it never raises OSError on its
    own when the receiver is unreachable — nothing bounds that wait except
    our own timeout. Simulate that by having the mocked create() hang
    indefinitely, and confirm setup still resolves to SETUP_RETRY rather
    than blocking forever.
    """
    async def _hang(*args, **kwargs) -> None:
        """Simulate Connection.create() never returning."""
        await asyncio.sleep(3600)

    with (
        patch(
            "homeassistant.components.anthemav.CONNECT_TIMEOUT_SECONDS",
            0.01,
        ),
        patch(
            "anthemav.Connection.create",
            side_effect=_hang,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_anthemav_dispatcher_signal(
    hass: HomeAssistant,
    mock_connection_create: AsyncMock,
    mock_anthemav: AsyncMock,
    init_integration: MockConfigEntry,
    update_callback: Callable[[str], None],
) -> None:
    """Test send update signal to dispatcher."""
    states = hass.states.get("media_player.anthem_av")
    assert states
    assert states.state == STATE_OFF

    # change state of the AVR
    mock_anthemav.protocol.zones[1].power = True

    update_callback("power")

    await hass.async_block_till_done()

    states = hass.states.get("media_player.anthem_av")
    assert states.state == STATE_ON
