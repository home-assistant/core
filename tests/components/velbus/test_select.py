"""Velbus select platform tests."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("set_program"), [("none"), ("summer"), ("winter"), ("holiday")]
)
async def test_select_program(
    hass: HomeAssistant,
    mock_select: AsyncMock,
    config_entry: MockConfigEntry,
    set_program: str,
) -> None:
    """Test program selection."""
    await init_integration(hass, config_entry)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.kitchen_select", ATTR_OPTION: set_program},
        blocking=True,
    )
    mock_select.set_selected_program.assert_called_once_with(set_program)
