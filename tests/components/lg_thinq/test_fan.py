"""Tests for the LG ThinQ fan platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

HOOD_FAN_ENTITY_ID = "fan.test_hood_hood"


@pytest.mark.parametrize("device_fixture", ["hood"])
async def test_fan_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.lg_thinq.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_fixture", "service", "service_data", "expected_value"),
    [
        ("hood", SERVICE_TURN_ON, {}, 1),
        ("hood", SERVICE_TURN_OFF, {}, 0),
        ("hood", SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 100}, 5),
        ("hood", SERVICE_TURN_ON, {ATTR_PERCENTAGE: 60}, 3),
        ("hood", SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 0}, 0),
    ],
)
async def test_fan_service_calls(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict,
    expected_value: int,
) -> None:
    """Test hood fan service calls post the correct speed values."""
    with patch("homeassistant.components.lg_thinq.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry)

    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    coordinator.api.post = AsyncMock()

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: HOOD_FAN_ENTITY_ID, **service_data},
        blocking=True,
    )

    coordinator.api.post.assert_awaited_once_with("fan_speed", expected_value)
