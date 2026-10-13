"""Test the Airobot diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture
def platforms() -> list[Platform]:
    """Diagnostics do not need any platform set up."""
    return [Platform.SENSOR]


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result == snapshot


async def test_vu_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_vu_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test VU config entry diagnostics."""
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, init_vu_integration
    )

    assert result == snapshot
