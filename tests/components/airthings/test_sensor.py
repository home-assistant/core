"""Test the Airthings sensors."""

from airthings import Airthings
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfRadiationConcentration
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_conversion import RadiationConcentrationConverter
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_device_types(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_airthings_client: Airthings,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all device types."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("airthings_fixture", ["view_plus", "wave_plus"])
@pytest.mark.parametrize(
    ("unit_system", "expected_unit", "expected_precision"),
    [
        (METRIC_SYSTEM, UnitOfRadiationConcentration.BECQUEREL_PER_CUBIC_METER, 0),
        (US_CUSTOMARY_SYSTEM, UnitOfRadiationConcentration.PICOCURIES_PER_LITER, 1),
    ],
)
async def test_radon_unit_matches_unit_system(
    hass: HomeAssistant,
    airthings_fixture: str,
    unit_system: UnitSystem,
    expected_unit: UnitOfRadiationConcentration,
    expected_precision: int,
    mock_config_entry: MockConfigEntry,
    mock_airthings_client: Airthings,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test radon sensors use the core radon device class conversion path."""
    hass.config.units = unit_system

    await setup_integration(hass, mock_config_entry)

    radon_entity = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id.endswith("_radonShortTermAvg")
    )
    state = hass.states.get(radon_entity.entity_id)

    assert state is not None
    assert state.attributes["device_class"] == SensorDeviceClass.RADON
    assert state.attributes["unit_of_measurement"] == expected_unit
    assert (
        radon_entity.options["sensor"]["suggested_display_precision"]
        == expected_precision
    )

    raw_state = mock_airthings_client.update_devices.return_value[
        radon_entity.unique_id.removesuffix("_radonShortTermAvg")
    ].sensors["radonShortTermAvg"]
    expected_state = RadiationConcentrationConverter.convert(
        raw_state,
        UnitOfRadiationConcentration.BECQUEREL_PER_CUBIC_METER,
        expected_unit,
    )

    assert float(state.state) == pytest.approx(expected_state)
