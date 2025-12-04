"""Tests for Entity Migration migrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.entity_migration.migrator import EntityMigrator
from homeassistant.components.entity_migration.models import (
    MigrationErrorType,
    Reference,
    ScanResult,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def migrator(hass: HomeAssistant) -> EntityMigrator:
    """Create an EntityMigrator instance."""
    return EntityMigrator(hass)


@pytest.fixture
def sample_scan_result(tmp_path: Path) -> ScanResult:
    """Create a sample scan result with file paths."""
    yaml_file = tmp_path / "automations.yaml"
    yaml_file.write_text(
        """
- id: test_auto
  trigger:
    entity_id: sensor.old_entity
  action:
    service: light.turn_on
"""
    )

    return ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="test_auto",
                    config_name="Test Automation",
                    location="trigger",
                    file_path=yaml_file,
                )
            ]
        },
        total_count=1,
    )


async def test_migrate_success(
    hass: HomeAssistant,
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test successful migration."""
    # Create test file
    yaml_file = tmp_path / "automations.yaml"
    yaml_file.write_text("entity_id: sensor.old_entity")

    # Mock hass.config.path to return tmp_path
    hass.config.config_dir = str(tmp_path)

    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="test_auto",
                    config_name="Test",
                    location="trigger",
                    file_path=yaml_file,
                )
            ]
        },
        total_count=1,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
    )

    assert result.success is True
    assert result.updated_count == 1
    assert len(result.errors) == 0
    assert result.dry_run is False

    # Verify file was updated
    content = yaml_file.read_text()
    assert "sensor.new_entity" in content
    assert "sensor.old_entity" not in content


async def test_migrate_dry_run(
    hass: HomeAssistant,
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test dry run doesn't modify files."""
    yaml_file = tmp_path / "automations.yaml"
    original_content = "entity_id: sensor.old_entity"
    yaml_file.write_text(original_content)

    hass.config.config_dir = str(tmp_path)

    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="test_auto",
                    config_name="Test",
                    location="trigger",
                    file_path=yaml_file,
                )
            ]
        },
        total_count=1,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
        dry_run=True,
    )

    assert result.success is True
    assert result.updated_count == 1
    assert result.dry_run is True

    # Verify file was NOT modified
    assert yaml_file.read_text() == original_content


async def test_migrate_creates_backup(
    hass: HomeAssistant,
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test migration creates backup when requested."""
    yaml_file = tmp_path / "automations.yaml"
    yaml_file.write_text("entity_id: sensor.old_entity")

    hass.config.config_dir = str(tmp_path)

    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="test_auto",
                    config_name="Test",
                    location="trigger",
                    file_path=yaml_file,
                )
            ]
        },
        total_count=1,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
        create_backup=True,
    )

    assert result.success is True
    assert result.backup_path is not None
    assert result.backup_path.exists()

    # Verify backup contains original content
    backup_files = list(result.backup_path.rglob("*"))
    assert len([f for f in backup_files if f.is_file()]) >= 1


async def test_migrate_empty_scan_result(
    hass: HomeAssistant,
    migrator: EntityMigrator,
) -> None:
    """Test migration with no references found."""
    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={},
        total_count=0,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
    )

    assert result.success is True
    assert result.updated_count == 0


async def test_migrate_triggers_reloads(
    hass: HomeAssistant,
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test migration triggers component reloads."""
    yaml_file = tmp_path / "automations.yaml"
    yaml_file.write_text("entity_id: sensor.old_entity")

    hass.config.config_dir = str(tmp_path)

    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="test_auto",
                    config_name="Test",
                    location="trigger",
                    file_path=yaml_file,
                )
            ]
        },
        total_count=1,
    )

    # Track service calls by patching at module level
    service_calls = []

    original_async_call = hass.services.async_call

    async def tracking_async_call(domain, service, *args, **kwargs):
        service_calls.append((domain, service))
        # Don't actually call the service in tests

    # Patch the _trigger_reloads method to track calls
    with patch.object(
        migrator,
        "_trigger_reloads",
        wraps=migrator._trigger_reloads,
    ) as mock_reload:
        # Also patch the hass.services.async_call via the migrator's hass reference
        with patch(
            "homeassistant.core.ServiceRegistry.async_call",
            side_effect=tracking_async_call,
        ):
            result = await migrator.async_migrate(
                "sensor.old_entity",
                "sensor.new_entity",
                scan_result,
            )

    assert result.success is True
    # Verify _trigger_reloads was called
    mock_reload.assert_called_once()


async def test_migrate_multiple_files(
    hass: HomeAssistant,
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test migration across multiple files."""
    auto_file = tmp_path / "automations.yaml"
    auto_file.write_text("entity_id: sensor.old_entity")

    script_file = tmp_path / "scripts.yaml"
    script_file.write_text("entity_id: sensor.old_entity")

    hass.config.config_dir = str(tmp_path)

    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="auto1",
                    config_name="Auto 1",
                    location="trigger",
                    file_path=auto_file,
                )
            ],
            "script": [
                Reference(
                    config_type="script",
                    config_id="script1",
                    config_name="Script 1",
                    location="sequence",
                    file_path=script_file,
                )
            ],
        },
        total_count=2,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
    )

    assert result.success is True
    assert result.updated_count == 2

    # Verify both files were updated
    assert "sensor.new_entity" in auto_file.read_text()
    assert "sensor.new_entity" in script_file.read_text()


async def test_migrate_json_file(
    hass: HomeAssistant,
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test migration of JSON storage files."""
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    json_file = storage_dir / "lovelace"
    json_file.write_text('{"entity": "sensor.old_entity"}')

    hass.config.config_dir = str(tmp_path)

    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "dashboard": [
                Reference(
                    config_type="dashboard",
                    config_id="lovelace",
                    config_name="Overview",
                    location="entity",
                    file_path=json_file,
                )
            ]
        },
        total_count=1,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
    )

    assert result.success is True
    assert result.updated_count == 1

    content = json_file.read_text()
    assert "sensor.new_entity" in content


async def test_migrate_result_as_dict(
    hass: HomeAssistant,
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test MigrationResult as_dict serialization."""
    yaml_file = tmp_path / "automations.yaml"
    yaml_file.write_text("entity_id: sensor.old_entity")

    hass.config.config_dir = str(tmp_path)

    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="test",
                    config_name="Test",
                    location="trigger",
                    file_path=yaml_file,
                )
            ]
        },
        total_count=1,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
        create_backup=True,
    )

    result_dict = result.as_dict()

    assert "success" in result_dict
    assert "source_entity_id" in result_dict
    assert "target_entity_id" in result_dict
    assert "updated" in result_dict
    assert "updated_count" in result_dict
    assert "errors" in result_dict
    assert "backup_path" in result_dict
    assert "dry_run" in result_dict


async def test_migrate_no_backup_on_dry_run(
    hass: HomeAssistant,
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test that backup is not created during dry run."""
    yaml_file = tmp_path / "automations.yaml"
    yaml_file.write_text("entity_id: sensor.old_entity")

    hass.config.config_dir = str(tmp_path)

    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="test",
                    config_name="Test",
                    location="trigger",
                    file_path=yaml_file,
                )
            ]
        },
        total_count=1,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
        create_backup=True,
        dry_run=True,
    )

    assert result.success is True
    assert result.backup_path is None  # No backup on dry run


async def test_collect_file_paths(
    migrator: EntityMigrator,
    tmp_path: Path,
) -> None:
    """Test file path collection from scan result."""
    file1 = tmp_path / "file1.yaml"
    file2 = tmp_path / "file2.yaml"
    file1.touch()
    file2.touch()

    scan_result = ScanResult(
        source_entity_id="sensor.test",
        references={
            "automation": [
                Reference("automation", "a1", "Auto 1", "trigger", file1),
                Reference("automation", "a2", "Auto 2", "action", file1),  # Same file
            ],
            "script": [
                Reference("script", "s1", "Script 1", "sequence", file2),
            ],
        },
        total_count=3,
    )

    file_paths = migrator._collect_file_paths(scan_result)

    # Should have 2 unique paths
    assert len(file_paths) == 2
    assert file1 in file_paths
    assert file2 in file_paths


async def test_get_config_type_from_path(
    migrator: EntityMigrator,
) -> None:
    """Test config type detection from file path."""
    assert (
        migrator._get_config_type_from_path(Path("/config/automations.yaml"))
        == "automation"
    )
    assert (
        migrator._get_config_type_from_path(Path("/config/scripts.yaml"))
        == "script"
    )
    assert (
        migrator._get_config_type_from_path(Path("/config/scenes.yaml"))
        == "scene"
    )
    assert (
        migrator._get_config_type_from_path(Path("/config/groups.yaml"))
        == "group"
    )
    # lovelace files are detected as dashboard
    assert (
        migrator._get_config_type_from_path(Path("/config/.storage/lovelace"))
        == "dashboard"
    )
    assert (
        migrator._get_config_type_from_path(Path("/config/.storage/core.entity_registry"))
        == "storage"
    )
    assert (
        migrator._get_config_type_from_path(Path("/config/custom.yaml"))
        == "yaml"
    )


async def test_migrate_references_without_file_path(
    hass: HomeAssistant,
    migrator: EntityMigrator,
) -> None:
    """Test migration handles references without file paths."""
    scan_result = ScanResult(
        source_entity_id="sensor.old_entity",
        references={
            "automation": [
                Reference(
                    config_type="automation",
                    config_id="ui_auto",
                    config_name="UI Automation",
                    location="trigger",
                    file_path=None,  # UI-based automation
                )
            ]
        },
        total_count=1,
    )

    result = await migrator.async_migrate(
        "sensor.old_entity",
        "sensor.new_entity",
        scan_result,
    )

    # Should succeed but with no updates (no file to modify)
    assert result.success is True
    assert result.updated_count == 0
