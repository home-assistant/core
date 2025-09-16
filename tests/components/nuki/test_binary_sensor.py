"""Tests for the nuki binary sensors."""

from unittest.mock import patch

import pytest
import requests_mock
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_nuki_requests: requests_mock.Mocker,
) -> None:
    """Test binary sensors."""
    with patch("homeassistant.components.nuki.PLATFORMS", [Platform.BINARY_SENSOR]):
        entry = await init_integration(hass, mock_nuki_requests)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
