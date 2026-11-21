"""Tests for the Apple TV diagnostics."""

from unittest.mock import AsyncMock

from pyatv.const import FeatureName, FeatureState
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_atv: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_atv.features.set_state(FeatureName.Artwork, FeatureState.Unavailable)
    mock_atv.features.set_state(FeatureName.Stop, FeatureState.Unsupported)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
