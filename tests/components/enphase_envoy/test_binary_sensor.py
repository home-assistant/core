"""Test Enphase Envoy binary sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("mock_envoy"),
    ["envoy_eu_batt", "envoy_metered_batt_relay"],
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
