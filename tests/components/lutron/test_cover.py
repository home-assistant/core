"""Test Lutron cover platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    STATE_CLOSED,
    STATE_OPEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_cover_setup(
    hass: HomeAssistant,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cover setup."""
    mock_config_entry.add_to_hass(hass)

    cover = mock_lutron.areas[0].outputs[2]
    cover.level = 0
    cover.last_level.return_value = 0

    with patch("homeassistant.components.lutron.PLATFORMS", [Platform.COVER]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_cover_services(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test cover services."""
    mock_config_entry.add_to_hass(hass)

    cover = mock_lutron.areas[0].outputs[2]
    cover.level = 0
    cover.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "cover.test_cover"

    # Open cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert cover.level == 100

    # Close cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert cover.level == 0

    # Set cover position
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, "position": 50},
        blocking=True,
    )
    assert cover.level == 50


async def test_cover_update(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test cover state update."""
    mock_config_entry.add_to_hass(hass)

    cover = mock_lutron.areas[0].outputs[2]
    cover.level = 0
    cover.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "cover.test_cover"
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # Simulate update
    cover.last_level.return_value = 100
    callback = cover.subscribe.call_args[0][0]
    callback(cover, None, None, None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OPEN
    assert hass.states.get(entity_id).attributes["current_position"] == 100
