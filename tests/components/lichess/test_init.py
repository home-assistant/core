"""Test the Lichess initialization."""

from unittest.mock import AsyncMock

from aiolichess.exceptions import AioLichessError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lichess.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lichess_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lichess device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device({(DOMAIN, "drnykterstien")})
    assert device
    assert device == snapshot


async def test_setup_entry_failed(
    hass: HomeAssistant,
    mock_lichess_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when API raises an error."""
    mock_lichess_client.get_statistics.side_effect = AioLichessError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
