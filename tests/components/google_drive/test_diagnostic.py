"""Test GIOS diagnostics."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

pytestmark = [
    pytest.mark.freeze_time("2021-11-04 17:36:59+01:00"),
]


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test config entry diagnostics."""
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [
                {
                    "id": "HA folder ID",
                    "name": "HA folder name",
                    "description": json.dumps(mock_agent_backup.as_dict()),
                    "size": str(int(mock_agent_backup.size)),
                }
            ]
        }
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
