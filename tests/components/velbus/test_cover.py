"""Velbus cover platform tests."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import ATTR_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    Platform,
)
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
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.COVER]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "entity_num"),
    [
        ("cover.covername", 0),
        ("cover.covernamenopos", 1),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    entity_num: int,
) -> None:
    """Test the cover actions."""
    await init_integration(hass, config_entry)
    entity = config_entry.runtime_data.controller.get_all_cover()[entity_num]
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    entity.close.assert_called_once()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    entity.open.assert_called_once()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    entity.stop.assert_called_once()


async def test_position(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_cover: AsyncMock,
) -> None:
    """Test the set_postion over action."""
    await init_integration(hass, config_entry)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.covername", ATTR_POSITION: 25},
        blocking=True,
    )
    mock_cover.set_position.assert_called_once_with(75)
