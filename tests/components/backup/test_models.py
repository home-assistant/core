"""Tests for the Backup integration."""

from homeassistant.components.backup import AgentBackup

from .common import TEST_BACKUP_ABC123


async def test_agent_backup_serialization() -> None:
    """Test AgentBackup serialization."""

    assert AgentBackup.from_dict(TEST_BACKUP_ABC123.as_dict()) == TEST_BACKUP_ABC123
