"""Test Volvo sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "full_model",
    ["ex30_2024", "s90_diesel_2018", "xc40_electric_2024", "xc90_petrol_2019"],
)
async def test_sensor(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "full_model",
    ["xc40_electric_2024"],
)
async def test_distance_to_empty_battery(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test using `distanceToEmptyBattery` instead of `electricRange`."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    assert hass.states.get("sensor.volvo_xc40_distance_to_empty_battery").state == "250"
