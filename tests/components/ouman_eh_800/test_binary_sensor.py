"""Tests for the Ouman EH-800 binary sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ouman_eh_800.const import DEFAULT_SCAN_INTERVAL_SECONDS
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize("init_integration", [Platform.BINARY_SENSOR], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the binary sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("init_integration", [Platform.BINARY_SENSOR], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_summer_function_state(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the summer function state follows the device on the next poll."""
    entity_id = "binary_sensor.heating_circuit_1_patterilammitys_summer_function"
    assert hass.states.get(entity_id).state == STATE_OFF

    mock_ouman_client.get_is_l1_summer_function_active.return_value = True
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON
