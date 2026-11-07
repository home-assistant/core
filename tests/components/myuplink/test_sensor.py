"""Tests for myuplink sensor module."""

from unittest.mock import MagicMock, patch

from myuplink import DevicePoint
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.myuplink.sensor import get_description
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import Platform, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


def _energy_point(parameter_id: str, category: str = "Energy Log") -> DevicePoint:
    """Return an energy device point."""
    return DevicePoint(
        {
            "category": category,
            "parameterId": parameter_id,
            "parameterName": "Energy",
            "parameterUnit": "kWh",
            "writable": False,
            "timestamp": "2026-11-05T08:50:00+00:00",
            "value": 0.5,
            "strVal": "0.5kWh",
            "smartHomeCategories": [],
            "minValue": None,
            "maxValue": None,
            "stepValue": 1,
            "enumValues": [],
            "scaleValue": "1",
            "zoneId": None,
        }
    )


@pytest.mark.parametrize(
    "parameter_id",
    ["25154", "25155", "25157", "25158", "25159", "25161", "25162", "25163"],
)
def test_past_hour_energy_has_no_state_class(parameter_id: str) -> None:
    """Test rolling one hour energy sensors do not use total_increasing."""
    description = get_description(_energy_point(parameter_id))

    assert description is not None
    assert description.state_class is None
    assert description.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR


def test_other_energy_keeps_total_increasing() -> None:
    """Test other energy log sensors keep total_increasing."""
    description = get_description(_energy_point("10077"))

    assert description is not None
    assert description.state_class is SensorStateClass.TOTAL_INCREASING


def test_past_hour_id_outside_energy_log_unchanged() -> None:
    """Test the same id in another category keeps total_increasing."""
    description = get_description(_energy_point("25154", category="NIBE S1155"))

    assert description is not None
    assert description.state_class is SensorStateClass.TOTAL_INCREASING


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor state."""

    with patch("homeassistant.components.myuplink.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)