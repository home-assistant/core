"""Tests for the Elmax covers."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform


async def test_covers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test covers."""
    with patch("homeassistant.components.elmax.ELMAX_PLATFORMS", [Platform.COVER]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
