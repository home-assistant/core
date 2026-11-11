"""Test RainMachine binary sensors."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rainmachine.const import DATA_ZONES, DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
) -> None:
    """Test binary sensors."""
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch(
            "homeassistant.components.rainmachine.PLATFORMS", [Platform.BINARY_SENSOR]
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    entity_id = "binary_sensor.12345_landscaping_restrictions"
    assert hass.states.get(entity_id).state == "off"
    coordinator = config_entry.runtime_data.coordinators[DATA_ZONES]
    zones = {**coordinator.data}
    zones[1] = {**zones[1], "restriction": True}
    coordinator.async_set_updated_data(zones)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
