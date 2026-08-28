"""Tests for the HDFury diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hdfury import PLATFORMS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HDFury diagnostics."""

    await setup_integration(hass, mock_config_entry, PLATFORMS)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics == snapshot
