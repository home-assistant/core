"""Tests for the LaMetric helpers."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.lametric.helpers import async_get_coordinator_by_device_id
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_get_coordinator_by_device_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test get LaMetric coordinator by device ID ."""
    with pytest.raises(
        ServiceValidationError, match="Device with ID bla was not found"
    ):
        async_get_coordinator_by_device_id(hass, "bla")

    entry = entity_registry.async_get("button.frenck_s_lametric_next_app")
    assert entry
    assert entry.device_id

    coordinator = async_get_coordinator_by_device_id(hass, entry.device_id)
    assert coordinator.data == mock_lametric.device.return_value

    # Unload entry
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="is not loaded"):
        async_get_coordinator_by_device_id(hass, entry.device_id)
