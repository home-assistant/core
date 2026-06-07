"""Test the Advantage Air Binary Sensor Platform."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config

from tests.common import snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_get: AsyncMock,
) -> None:
    """Test binary sensor platform."""

    entry = await add_mock_config(hass, [Platform.BINARY_SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
