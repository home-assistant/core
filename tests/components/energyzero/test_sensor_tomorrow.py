"""Tests for the sensors provided by the EnergyZero integration."""
from unittest.mock import MagicMock

from energyzero import EnergyZeroNoDataError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.energyzero.const import DOMAIN
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

pytestmark = [pytest.mark.freeze_time("2022-12-07 15:00:00")]


@pytest.mark.parametrize(
    ("entity_id", "entity_unique_id", "device_identifier"),
    [
        (
            "sensor.energyzero_tomorrow_energy_average_price",
            "tomorrow_energy_average_price",
            "tomorrow_energy",
        ),
        (
            "sensor.energyzero_tomorrow_energy_max_price",
            "tomorrow_energy_max_price",
            "tomorrow_energy",
        ),
        (
            "sensor.energyzero_tomorrow_energy_highest_price_time",
            "tomorrow_energy_highest_price_time",
            "tomorrow_energy",
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
    entity_unique_id: str,
    device_identifier: str,
) -> None:
    """Test the EnergyZero - Energy sensors."""
    entry_id = init_integration.entry_id
    assert (state := hass.states.get(entity_id))
    assert state == snapshot
    assert (entity_entry := entity_registry.async_get(entity_id))
    assert entity_entry == snapshot(exclude=props("unique_id"))
    assert entity_entry.unique_id == f"{entry_id}_{entity_unique_id}"

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot(exclude=props("identifiers"))
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_{device_identifier}")}
