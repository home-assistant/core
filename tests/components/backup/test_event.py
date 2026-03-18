"""The tests for the Backup event entity."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.backup.const import DOMAIN
from homeassistant.components.backup.event import ATTR_BACKUP_STAGE, ATTR_FAILED_REASON
from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_backup_integration

from tests.common import snapshot_platform
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("mock_backup_generation")
async def test_event_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test automatic backup event entity."""
    with patch("homeassistant.components.backup.PLATFORMS", [Platform.EVENT]):
        await setup_backup_integration(hass, with_hassio=False)
        await hass.async_block_till_done(wait_background_tasks=True)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("mock_backup_generation")
async def test_event_entity_backup_completed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test completed automatic backup event."""
    with patch("homeassistant.components.backup.PLATFORMS", [Platform.EVENT]):
        await setup_backup_integration(hass, with_hassio=False)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("event.backup_automatic_backup")
    assert state.attributes[ATTR_EVENT_TYPE] is None

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()
    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["backup.local"]}
    )
    assert await client.receive_json()

    state = hass.states.get("event.backup_automatic_backup")
    assert state.attributes[ATTR_EVENT_TYPE] == "in_progress"
    assert state.attributes[ATTR_BACKUP_STAGE] is not None
    assert state.attributes[ATTR_FAILED_REASON] is None

    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("event.backup_automatic_backup")
    assert state.attributes[ATTR_EVENT_TYPE] == "completed"
    assert state.attributes[ATTR_BACKUP_STAGE] is None
    assert state.attributes[ATTR_FAILED_REASON] is None


@pytest.mark.usefixtures("mock_backup_generation")
async def test_event_entity_backup_failed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    create_backup: AsyncMock,
) -> None:
    """Test failed automatic backup event."""
    with patch("homeassistant.components.backup.PLATFORMS", [Platform.EVENT]):
        await setup_backup_integration(hass, with_hassio=False)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("event.backup_automatic_backup")
    assert state.attributes[ATTR_EVENT_TYPE] is None

    create_backup.side_effect = Exception("Boom!")

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()
    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["backup.local"]}
    )
    assert await client.receive_json()

    state = hass.states.get("event.backup_automatic_backup")
    assert state.attributes[ATTR_EVENT_TYPE] == "failed"
    assert state.attributes[ATTR_BACKUP_STAGE] is None
    assert state.attributes[ATTR_FAILED_REASON] == "unknown_error"
