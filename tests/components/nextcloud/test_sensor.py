"""Tests for the Nextcloud sensors."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .const import NC_DATA, VALID_CONFIG

from tests.common import snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_async_setup_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a successful setup entry."""
    with patch("homeassistant.components.nextcloud.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass, VALID_CONFIG, NC_DATA)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
