"""Test Linear Garage Door cover."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_covers(
    hass: HomeAssistant,
    mock_linear: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that data gets parsed and returned appropriately."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_open_cover(
    hass: HomeAssistant, mock_linear: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that opening the cover works as intended."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_garage_1"},
        blocking=True,
    )

    assert mock_linear.operate_device.call_count == 0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_garage_2"},
        blocking=True,
    )

    assert mock_linear.operate_device.call_count == 1


async def test_close_cover(
    hass: HomeAssistant, mock_linear: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that closing the cover works as intended."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_garage_2"},
        blocking=True,
    )

    assert mock_linear.operate_device.call_count == 0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_garage_1"},
        blocking=True,
    )

    assert mock_linear.operate_device.call_count == 1
