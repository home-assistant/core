"""Test for the sensor platform entity of the fujitsu_fglair component."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test that coordinator returns the data we expect after the first refresh."""
    assert await integration_setup()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
