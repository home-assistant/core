"""Tests for Entity Migration file updaters."""

from __future__ import annotations

from pathlib import Path

import pytest

from homeassistant.components.entity_migration.updaters import (
    JSONStorageUpdater,
    YAMLFileUpdater,
)


class TestYAMLFileUpdater:
    """Tests for YAMLFileUpdater."""

    @pytest.fixture
    def updater(self) -> YAMLFileUpdater:
        """Create a YAMLFileUpdater instance."""
        return YAMLFileUpdater()

    async def test_can_handle_yaml(self, updater: YAMLFileUpdater) -> None:
        """Test can_handle returns True for YAML files."""
        assert updater.can_handle(Path("/config/automations.yaml"))
        assert updater.can_handle(Path("/config/scripts.yml"))
        assert updater.can_handle(Path("/config/configuration.YAML"))

    async def test_can_handle_non_yaml(self, updater: YAMLFileUpdater) -> None:
        """Test can_handle returns False for non-YAML files."""
        assert not updater.can_handle(Path("/config/data.json"))
        assert not updater.can_handle(Path("/config/.storage/core.entity_registry"))

    async def test_update_simple_entity_id(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test updating a simple entity ID in YAML."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            """
- id: test_automation
  trigger:
    - platform: state
      entity_id: sensor.old_entity
  action:
    - service: light.turn_on
      target:
        entity_id: light.living_room
"""
        )

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 1

        content = yaml_file.read_text()
        assert "sensor.new_entity" in content
        assert "sensor.old_entity" not in content
        # Ensure unrelated entity IDs are not changed
        assert "light.living_room" in content

    async def test_update_entity_in_list(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test updating entity ID in a list."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            """
entities:
  - sensor.old_entity
  - sensor.other_entity
  - binary_sensor.test
"""
        )

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 1

        content = yaml_file.read_text()
        assert "sensor.new_entity" in content
        assert "sensor.old_entity" not in content
        assert "sensor.other_entity" in content

    async def test_update_preserves_comments(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test that YAML comments are preserved after update."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            """# This is a comment
automation:
  - id: test  # inline comment
    trigger:
      # Comment about trigger
      entity_id: sensor.old_entity
"""
        )

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True

        content = yaml_file.read_text()
        assert "# This is a comment" in content
        assert "# inline comment" in content
        assert "# Comment about trigger" in content

    async def test_update_entity_in_template(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test updating entity ID within a Jinja2 template."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            """
template:
  - sensor:
      - state: "{{ states('sensor.old_entity') }}"
        name: "Test Sensor"
"""
        )

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 1

        content = yaml_file.read_text()
        assert "states('sensor.new_entity')" in content

    async def test_update_multiple_occurrences(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test updating multiple occurrences of the same entity ID."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            """
automation:
  - trigger:
      entity_id: sensor.old_entity
    condition:
      entity_id: sensor.old_entity
    action:
      entity_id: sensor.old_entity
"""
        )

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 3

        content = yaml_file.read_text()
        assert content.count("sensor.new_entity") == 3
        assert "sensor.old_entity" not in content

    async def test_update_no_changes(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test update when entity ID is not present."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            """
automation:
  - trigger:
      entity_id: sensor.other_entity
"""
        )

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 0

    async def test_update_empty_file(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test update on empty YAML file."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("")

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 0

    async def test_update_dry_run(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test dry run doesn't modify file."""
        yaml_file = tmp_path / "test.yaml"
        original_content = """
trigger:
  entity_id: sensor.old_entity
"""
        yaml_file.write_text(original_content)

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
            dry_run=True,
        )

        assert result.success is True
        assert result.changes_made == 1
        # File should not be modified
        assert yaml_file.read_text() == original_content

    async def test_update_invalid_yaml(
        self, updater: YAMLFileUpdater, tmp_path: Path
    ) -> None:
        """Test handling of invalid YAML after replacement."""
        yaml_file = tmp_path / "test.yaml"
        # Write YAML that contains the entity but becomes invalid after replacement
        # (This tests validation of the result)
        yaml_file.write_text("entity: sensor.old_entity\n{{invalid yaml")

        result = await updater.async_update(
            yaml_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is False
        assert result.error is not None


class TestJSONStorageUpdater:
    """Tests for JSONStorageUpdater."""

    @pytest.fixture
    def updater(self) -> JSONStorageUpdater:
        """Create a JSONStorageUpdater instance."""
        return JSONStorageUpdater()

    async def test_can_handle_json(self, updater: JSONStorageUpdater) -> None:
        """Test can_handle returns True for JSON files."""
        assert updater.can_handle(Path("/config/data.json"))
        assert updater.can_handle(Path("/config/.storage/core.entity_registry"))
        assert updater.can_handle(Path("/config/.storage/lovelace"))

    async def test_can_handle_non_json(self, updater: JSONStorageUpdater) -> None:
        """Test can_handle returns False for non-JSON files."""
        assert not updater.can_handle(Path("/config/automations.yaml"))
        assert not updater.can_handle(Path("/config/scripts.yml"))

    async def test_update_simple_entity_id(
        self, updater: JSONStorageUpdater, tmp_path: Path
    ) -> None:
        """Test updating a simple entity ID in JSON."""
        json_file = tmp_path / "test.json"
        json_file.write_text(
            """
{
    "version": 1,
    "data": {
        "entities": ["sensor.old_entity", "light.living_room"]
    }
}
"""
        )

        result = await updater.async_update(
            json_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 1

        import json

        data = json.loads(json_file.read_text())
        assert "sensor.new_entity" in data["data"]["entities"]
        assert "sensor.old_entity" not in data["data"]["entities"]
        assert "light.living_room" in data["data"]["entities"]

    async def test_update_nested_structure(
        self, updater: JSONStorageUpdater, tmp_path: Path
    ) -> None:
        """Test updating entity ID in nested JSON structure."""
        json_file = tmp_path / "test.json"
        json_file.write_text(
            """
{
    "views": [
        {
            "cards": [
                {
                    "type": "entity",
                    "entity": "sensor.old_entity"
                }
            ]
        }
    ]
}
"""
        )

        result = await updater.async_update(
            json_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 1

        import json

        data = json.loads(json_file.read_text())
        assert data["views"][0]["cards"][0]["entity"] == "sensor.new_entity"

    async def test_update_entity_as_key(
        self, updater: JSONStorageUpdater, tmp_path: Path
    ) -> None:
        """Test updating entity ID used as a dictionary key."""
        json_file = tmp_path / "test.json"
        json_file.write_text(
            """
{
    "entities": {
        "sensor.old_entity": {
            "state": "on"
        }
    }
}
"""
        )

        result = await updater.async_update(
            json_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 1

        import json

        data = json.loads(json_file.read_text())
        assert "sensor.new_entity" in data["entities"]
        assert "sensor.old_entity" not in data["entities"]

    async def test_update_multiple_occurrences(
        self, updater: JSONStorageUpdater, tmp_path: Path
    ) -> None:
        """Test updating multiple occurrences in JSON."""
        json_file = tmp_path / "test.json"
        json_file.write_text(
            """
{
    "trigger": {"entity_id": "sensor.old_entity"},
    "condition": {"entity_id": "sensor.old_entity"},
    "action": {"entity_id": "sensor.old_entity"}
}
"""
        )

        result = await updater.async_update(
            json_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 3

    async def test_update_no_changes(
        self, updater: JSONStorageUpdater, tmp_path: Path
    ) -> None:
        """Test update when entity ID is not present."""
        json_file = tmp_path / "test.json"
        json_file.write_text(
            """
{
    "entity": "sensor.other_entity"
}
"""
        )

        result = await updater.async_update(
            json_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True
        assert result.changes_made == 0

    async def test_update_dry_run(
        self, updater: JSONStorageUpdater, tmp_path: Path
    ) -> None:
        """Test dry run doesn't modify file."""
        json_file = tmp_path / "test.json"
        original_content = '{"entity": "sensor.old_entity"}'
        json_file.write_text(original_content)

        result = await updater.async_update(
            json_file,
            "sensor.old_entity",
            "sensor.new_entity",
            dry_run=True,
        )

        assert result.success is True
        assert result.changes_made == 1
        # File should not be modified
        assert json_file.read_text() == original_content

    async def test_update_invalid_json(
        self, updater: JSONStorageUpdater, tmp_path: Path
    ) -> None:
        """Test handling of invalid JSON."""
        json_file = tmp_path / "test.json"
        json_file.write_text("{invalid json")

        result = await updater.async_update(
            json_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is False
        assert result.error is not None
        assert "Invalid JSON" in result.error

    async def test_update_preserves_json_structure(
        self, updater: JSONStorageUpdater, tmp_path: Path
    ) -> None:
        """Test that JSON structure is preserved after update."""
        json_file = tmp_path / "test.json"
        json_file.write_text(
            """
{
    "version": 1,
    "minor_version": 2,
    "key": "lovelace",
    "data": {
        "config": {
            "views": [
                {"entity": "sensor.old_entity"}
            ]
        }
    }
}
"""
        )

        result = await updater.async_update(
            json_file,
            "sensor.old_entity",
            "sensor.new_entity",
        )

        assert result.success is True

        import json

        data = json.loads(json_file.read_text())
        assert data["version"] == 1
        assert data["minor_version"] == 2
        assert data["key"] == "lovelace"
        assert data["data"]["config"]["views"][0]["entity"] == "sensor.new_entity"


class TestUpdateResult:
    """Tests for UpdateResult dataclass."""

    async def test_update_result_as_dict(self, tmp_path: Path) -> None:
        """Test UpdateResult as_dict serialization."""
        from homeassistant.components.entity_migration.models import UpdateResult

        result = UpdateResult(
            success=True,
            file_path=tmp_path / "test.yaml",
            changes_made=5,
            error=None,
        )

        result_dict = result.as_dict()

        assert result_dict["success"] is True
        assert str(tmp_path) in result_dict["file_path"]
        assert result_dict["changes_made"] == 5
        assert result_dict["error"] is None

    async def test_update_result_with_error(self, tmp_path: Path) -> None:
        """Test UpdateResult with error."""
        from homeassistant.components.entity_migration.models import UpdateResult

        result = UpdateResult(
            success=False,
            file_path=tmp_path / "test.yaml",
            changes_made=0,
            error="File not found",
        )

        result_dict = result.as_dict()

        assert result_dict["success"] is False
        assert result_dict["error"] == "File not found"
