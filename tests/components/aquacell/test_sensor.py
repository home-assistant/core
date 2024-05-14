"""Test the Aquacell init module."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.aquacell import DSN, setup_integration


@pytest.mark.parametrize(
    ("sensor_id"),
    [
        ("wi_fi_level"),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    sensor_id: str,
) -> None:
    """Test the creation of Aquacell sensors."""
    await setup_integration(hass, mock_config_entry)
    entity_id = f"sensor.aquacell_name_{sensor_id}"

    assert entity_registry.async_is_registered(entity_id)
    entry = entity_registry.async_get(entity_id)
    assert entry.unique_id == f"{DSN}-{sensor_id}"
    assert hass.states.get(entity_id).state == "high"
