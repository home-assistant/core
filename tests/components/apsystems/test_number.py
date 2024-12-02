"""Test the APSystem number module."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_command(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
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
