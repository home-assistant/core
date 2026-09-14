"""Tests for the diagnostics data provided by the AirGradient integration."""

from unittest.mock import AsyncMock

from airgradient import ApiVersion
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import async_load_config_fixture, setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics_polling_instance(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_v1_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test V1 diagnostics."""
    mock_v1_airgradient_client.get_config.return_value = (
        await async_load_config_fixture(hass, "config_v1_local.json", ApiVersion.V1)
    )
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
