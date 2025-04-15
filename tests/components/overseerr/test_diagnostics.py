"""Tests for the diagnostics data provided by the Overseerr integration."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics_polling_instance(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_diagnostics_webhook_instance(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_overseerr_client_cloudhook: AsyncMock,
    mock_cloudhook_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, mock_cloudhook_config_entry)

    assert (
        await get_diagnostics_for_config_entry(
            hass, hass_client, mock_cloudhook_config_entry
        )
        == snapshot
    )
