"""Test the Tessie binary sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tessie.binary_sensor import VEHICLE_DESCRIPTIONS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import StateType

from .common import assert_entities, setup_platform


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Charging", True),
        ("Stopped", False),
        (True, True),
        (False, False),
        ("Unexpected", False),
    ],
)
def test_charging_binary_sensor_state(value: StateType, expected: bool) -> None:
    """Test charging binary sensor state conversion."""
    description = next(
        description
        for description in VEHICLE_DESCRIPTIONS
        if description.key == "charge_state_charging_state"
    )
    assert description.is_on(value) is expected


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the binary sensor entities are correct."""

    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)
