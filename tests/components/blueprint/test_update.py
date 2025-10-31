"""Tests for blueprint update entities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import automation, script
from homeassistant.components.blueprint import importer, models
from homeassistant.components.blueprint.const import DOMAIN as BLUEPRINT_DOMAIN
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as yaml_util


@pytest.fixture(autouse=True)
async def setup_blueprint_component(hass):
    """Ensure the blueprint integration is set up for each test."""
    assert await async_setup_component(hass, BLUEPRINT_DOMAIN, {})


async def test_automation_blueprint_update_entity_reloads(hass) -> None:
    """Test that updating an automation blueprint refreshes YAML and reloads automations."""
    source_url = "https://example.com/blueprints/automation/test.yaml"
    blueprint_rel_path = "test_namespace/test_automation.yaml"
    blueprint_file = Path(
        hass.config.path("blueprints", automation.DOMAIN, blueprint_rel_path)
    )
    blueprint_file.parent.mkdir(parents=True, exist_ok=True)

    initial_yaml = (
        "blueprint:\n"
        "  name: Test automation blueprint\n"
        "  description: Initial version\n"
        "  domain: automation\n"
        f"  source_url: {source_url}\n"
        "  input: {}\n"
        "trigger:\n"
        "  - platform: event\n"
        "    event_type: test_event\n"
        "action:\n"
        "  - service: test.initial_service\n"
    )
    blueprint_file.write_text(initial_yaml, encoding="utf-8")

    with patch(
        "homeassistant.components.automation.helpers._reload_blueprint_automations",
        new_callable=AsyncMock,
    ) as mock_reload:
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "use_blueprint": {
                        "path": blueprint_rel_path,
                        "input": {},
                    }
                }
            },
        )

        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        unique_id = f"{automation.DOMAIN}:{blueprint_rel_path}"
        entity_id = entity_registry.async_get_entity_id(
            UPDATE_DOMAIN, BLUEPRINT_DOMAIN, unique_id
        )
        assert entity_id is not None

        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"
        assert state.attributes.get("source_url") == source_url

        updated_yaml = (
            "blueprint:\n"
            "  name: Test automation blueprint\n"
            "  description: Updated version\n"
            "  domain: automation\n"
            f"  source_url: {source_url}\n"
            "  input: {}\n"
            "trigger:\n"
            "  - platform: event\n"
            "    event_type: test_event\n"
            "action:\n"
            "  - service: test.new_service\n"
        )
        updated_data = yaml_util.parse_yaml(updated_yaml)
        new_blueprint = models.Blueprint(
            updated_data,
            expected_domain=automation.DOMAIN,
            path=blueprint_rel_path,
            schema=automation.config.AUTOMATION_BLUEPRINT_SCHEMA,
        )
        imported_blueprint = importer.ImportedBlueprint(
            blueprint_rel_path.removesuffix(".yaml"), updated_yaml, new_blueprint
        )

        with patch(
            "homeassistant.components.blueprint.importer.fetch_blueprint_from_url",
            new=AsyncMock(return_value=imported_blueprint),
        ) as mock_fetch:
            await hass.services.async_call(
                UPDATE_DOMAIN,
                "install",
                {"entity_id": entity_id},
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_fetch.assert_awaited_once_with(hass, source_url)
        mock_reload.assert_awaited_once_with(hass, blueprint_rel_path)
        assert "test.new_service" in blueprint_file.read_text(encoding="utf-8")


async def test_script_blueprint_update_entity_reloads(hass) -> None:
    """Test that updating a script blueprint refreshes YAML and reloads scripts."""
    source_url = "https://example.com/blueprints/script/test.yaml"
    blueprint_rel_path = "test_namespace/test_script.yaml"
    blueprint_file = Path(
        hass.config.path("blueprints", script.DOMAIN, blueprint_rel_path)
    )
    blueprint_file.parent.mkdir(parents=True, exist_ok=True)

    initial_yaml = (
        "blueprint:\n"
        "  name: Test script blueprint\n"
        "  description: Initial version\n"
        "  domain: script\n"
        f"  source_url: {source_url}\n"
        "  input: {}\n"
        "sequence:\n"
        "  - event: test_event\n"
    )
    blueprint_file.write_text(initial_yaml, encoding="utf-8")

    with patch(
        "homeassistant.components.script.helpers._reload_blueprint_scripts",
        new_callable=AsyncMock,
    ) as mock_reload:
        assert await async_setup_component(
            hass,
            script.DOMAIN,
            {
                script.DOMAIN: {
                    "test_script": {
                        "use_blueprint": {
                            "path": blueprint_rel_path,
                            "input": {},
                        }
                    }
                }
            },
        )

        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        unique_id = f"{script.DOMAIN}:{blueprint_rel_path}"
        entity_id = entity_registry.async_get_entity_id(
            UPDATE_DOMAIN, BLUEPRINT_DOMAIN, unique_id
        )
        assert entity_id is not None

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"
        assert state.attributes.get("source_url") == source_url

        updated_yaml = (
            "blueprint:\n"
            "  name: Test script blueprint\n"
            "  description: Updated version\n"
            "  domain: script\n"
            f"  source_url: {source_url}\n"
            "  input: {}\n"
            "sequence:\n"
            "  - event: updated_event\n"
        )
        updated_data = yaml_util.parse_yaml(updated_yaml)
        new_blueprint = models.Blueprint(
            updated_data,
            expected_domain=script.DOMAIN,
            path=blueprint_rel_path,
            schema=BLUEPRINT_SCHEMA,
        )
        imported_blueprint = importer.ImportedBlueprint(
            blueprint_rel_path.removesuffix(".yaml"), updated_yaml, new_blueprint
        )

        with patch(
            "homeassistant.components.blueprint.importer.fetch_blueprint_from_url",
            new=AsyncMock(return_value=imported_blueprint),
        ) as mock_fetch:
            await hass.services.async_call(
                UPDATE_DOMAIN,
                "install",
                {"entity_id": entity_id},
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_fetch.assert_awaited_once_with(hass, source_url)
        mock_reload.assert_awaited_once_with(hass, blueprint_rel_path)
        assert "updated_event" in blueprint_file.read_text(encoding="utf-8")


async def test_blueprint_without_source_has_no_update_entity(hass) -> None:
    """Ensure blueprints without a source URL do not expose update entities."""
    blueprint_rel_path = "test_namespace/without_source.yaml"
    blueprint_file = Path(
        hass.config.path("blueprints", automation.DOMAIN, blueprint_rel_path)
    )
    blueprint_file.parent.mkdir(parents=True, exist_ok=True)

    yaml_without_source = (
        "blueprint:\n"
        "  name: No source blueprint\n"
        "  description: No source\n"
        "  domain: automation\n"
        "  input: {}\n"
        "trigger:\n"
        "  - platform: event\n"
        "    event_type: test_event\n"
        "action:\n"
        "  - service: test.service\n"
    )
    blueprint_file.write_text(yaml_without_source, encoding="utf-8")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "use_blueprint": {
                    "path": blueprint_rel_path,
                    "input": {},
                }
            }
        },
    )

    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    unique_id = f"{automation.DOMAIN}:{blueprint_rel_path}"
    assert (
        entity_registry.async_get_entity_id(UPDATE_DOMAIN, BLUEPRINT_DOMAIN, unique_id)
        is None
    )
