"""Tests for the Moehlenhoff Alpha2 buttons."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform


async def test_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test buttons."""
    with patch(
        "homeassistant.components.moehlenhoff_alpha2.PLATFORMS",
        [Platform.BUTTON],
    ):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
