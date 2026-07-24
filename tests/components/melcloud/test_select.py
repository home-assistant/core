"""Test the MELCloud select platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform

OPERATION_MODE_ENTITY = "select.ecodan_zone_1_operation_mode"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_get_devices")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all select entities with snapshot."""
    await setup_platform(hass, mock_config_entry, [Platform.SELECT])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_get_devices")
async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Selecting an option calls the library setter."""
    await setup_platform(hass, mock_config_entry, [Platform.SELECT])
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: OPERATION_MODE_ENTITY, ATTR_OPTION: "curve"},
        blocking=True,
    )
    mock_atw_device.zones[0].set_operation_mode.assert_awaited_once_with("curve")


@pytest.mark.usefixtures("mock_get_devices")
async def test_current_option_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """An operation mode outside the available options reports unknown."""
    mock_atw_device.zones[0].operation_mode = "unknown"
    await setup_platform(hass, mock_config_entry, [Platform.SELECT])
    state = hass.states.get(OPERATION_MODE_ENTITY)
    assert state is not None
    assert state.state == STATE_UNKNOWN
