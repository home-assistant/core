"""Test the Immich sensor platform."""

from unittest.mock import Mock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.immich.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_CONFIG_ENTRY_DATA

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_immich: Mock,
) -> None:
    """Test the Immich sensor platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA,
        entry_id="abcdef0123456789",
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.SENSOR]),
        patch(
            "homeassistant.components.immich.Immich",
            return_value=mock_immich,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
