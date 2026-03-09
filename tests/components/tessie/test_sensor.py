"""Test the Tessie sensor platform."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tessie.sensor import charge_state_to_option
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import StateType

from .common import assert_entities, setup_platform


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Charging", "charging"),
        (True, "charging"),
        (False, "stopped"),
        ("Unexpected", None),
    ],
)
def test_charge_state_to_option(value: StateType, expected: str | None) -> None:
    """Test charge state conversion for enum sensor values."""
    assert charge_state_to_option(value) == expected


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests that the sensor entities are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    entry = await setup_platform(hass, [Platform.SENSOR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)
