"""Test the APSystem number module."""

import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SCAN_INTERVAL = datetime.timedelta(seconds=30)


async def test_number(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test number command."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "number.mock_title_max_output"
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 50.1},
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_apsystems.set_max_power.assert_called_once_with(50)
    mock_apsystems.get_max_power.return_value = 50
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "50"
    mock_apsystems.get_max_power.side_effect = TimeoutError()
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 50.1},
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_apsystems")
@patch("homeassistant.components.apsystems.PLATFORMS", [Platform.NUMBER])
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
