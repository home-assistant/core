"""Test the Nina diagnostics."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test diagnostics."""

    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
