"""Tests for the Plugwise binary_sensor integration."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("platforms", [(BINARY_SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_binary_sensor_snapshot(
    hass: HomeAssistant,
    mock_smile_adam: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam binary_sensor snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
@pytest.mark.parametrize("platforms", [(BINARY_SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_anna_binary_sensor_snapshot(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Anna binary_sensor snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
async def test_anna_climate_binary_sensor_change(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test change of climate related binary_sensor entities."""
    hass.states.async_set("binary_sensor.opentherm_dhw_state", STATE_ON, {})
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.opentherm_dhw_state")
    assert state
    assert state.state == STATE_ON

    await async_update_entity(hass, "binary_sensor.opentherm_dhw_state")
    state = hass.states.get("binary_sensor.opentherm_dhw_state")
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize("chosen_env", ["p1v4_442_triple"], indirect=True)
@pytest.mark.parametrize(
    "gateway_id", ["03e65b16e4b247a29ae0d75a78cb492e"], indirect=True
)
@pytest.mark.parametrize("platforms", [(BINARY_SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_p1_v4_binary_sensor_snapshot(
    hass: HomeAssistant,
    mock_smile_p1: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Smile P1 binary_sensor snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)
