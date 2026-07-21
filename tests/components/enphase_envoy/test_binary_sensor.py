"""Test Enphase Envoy binary sensors."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.enphase_envoy.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize(
    ("mock_envoy"),
    ["envoy_eu_batt", "envoy_metered_batt_relay", "envoy_acb_batt"],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor platform entities against snapshot."""
    with patch(
        "homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=["mock_envoy"],
)
async def test_no_binary_sensor(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch platform entities are not created."""
    with patch(
        "homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, config_entry)
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_envoy"), ["envoy_metered_batt_relay"], indirect=["mock_envoy"]
)
async def test_binary_sensor_data(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor entities values and names."""
    with patch(
        "homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.data.enpower.serial_number
    entity_base = f"{Platform.BINARY_SENSOR}.enpower"

    assert (entity_state := hass.states.get(f"{entity_base}_{sn}_communicating"))
    assert entity_state.state == STATE_ON
    assert (entity_state := hass.states.get(f"{entity_base}_{sn}_grid_status"))
    assert entity_state.state == STATE_ON

    entity_base = f"{Platform.BINARY_SENSOR}.encharge"

    for sn in mock_envoy.data.encharge_inventory:
        assert (entity_state := hass.states.get(f"{entity_base}_{sn}_communicating"))
        assert entity_state.state == STATE_ON
        assert (entity_state := hass.states.get(f"{entity_base}_{sn}_dc_switch"))
        assert entity_state.state == STATE_ON


@pytest.mark.parametrize("mock_envoy", ["envoy_acb_batt"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_acb_battery_removed_from_inventory(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test ACB binary sensor is unknown when its serial leaves the inventory."""
    with patch(
        "homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, config_entry)

    entity_id = "binary_sensor.ac_battery_121000000001_communicating"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    mock_envoy.data.acb_inventory.pop("121000000001")
    mock_envoy.data.raw = {"changed": True}
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN
