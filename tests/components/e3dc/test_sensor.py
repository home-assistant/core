"""Tests for the E3/DC sensor platform."""

from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import seed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("holding", "entity_ids"),
    [
        pytest.param(
            {40088: 0},
            [
                "sensor.e3_dc_s10_x_wallbox_power",
                "sensor.e3_dc_s10_x_wallbox_solar_power",
            ],
            id="no_wallbox",
        ),
        pytest.param(
            {40109: 0},
            ["sensor.e3_dc_s10_x_additional_feeder_power"],
            id="no_additional_feeder",
        ),
        pytest.param(
            {40084: 0},
            ["sensor.e3_dc_s10_x_emergency_power"],
            id="no_emergency_power",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_optional_hardware_missing(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    holding: dict[int, int | list[int]],
    entity_ids: list[str],
) -> None:
    """Test sensors for hardware the power station lacks are not created."""
    seed(mock_unit, holding)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.e3_dc_s10_x_pv_power") is not None
    for entity_id in entity_ids:
        assert entity_registry.async_get(entity_id) is None
