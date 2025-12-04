"""Test Qbus binary sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensor(
    hass: HomeAssistant,
    setup_integration_deferred: Callable[[], Awaitable],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor."""

    with patch("homeassistant.components.qbus.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration_deferred()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
