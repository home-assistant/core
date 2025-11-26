"""Tests for the Entity Migration scanner."""

from __future__ import annotations

from homeassistant.components.entity_migration.const import (
    CONFIG_TYPE_AUTOMATION,
    CONFIG_TYPE_GROUP,
    CONFIG_TYPE_PERSON,
    CONFIG_TYPE_SCENE,
    CONFIG_TYPE_SCRIPT,
)
from homeassistant.components.entity_migration.scanner import EntityMigrationScanner
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_scan_empty_results(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scanning an entity with no references."""
    hass.states.async_set("sensor.test_entity", "on")

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("sensor.test_entity")

    assert result.source_entity_id == "sensor.test_entity"
    assert result.total_count == 0
    assert result.references == {}


async def test_scan_automation_references(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scanning finds automation references."""
    # Create test entities
    hass.states.async_set("sensor.temperature", "21")
    hass.states.async_set(
        "automation.morning_routine",
        "on",
        {"friendly_name": "Morning Routine"},
    )

    # Mock automation helper to return our automation
    mock_all_helpers["automations"].return_value = ["automation.morning_routine"]

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("sensor.temperature")

    assert result.total_count == 1
    assert CONFIG_TYPE_AUTOMATION in result.references
    assert len(result.references[CONFIG_TYPE_AUTOMATION]) == 1

    ref = result.references[CONFIG_TYPE_AUTOMATION][0]
    assert ref.config_type == CONFIG_TYPE_AUTOMATION
    assert ref.config_name == "Morning Routine"


async def test_scan_script_references(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scanning finds script references."""
    hass.states.async_set("light.living_room", "on")
    hass.states.async_set(
        "script.lights_off",
        "off",
        {"friendly_name": "Turn Off Lights"},
    )

    mock_all_helpers["scripts"].return_value = ["script.lights_off"]

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("light.living_room")

    assert result.total_count == 1
    assert CONFIG_TYPE_SCRIPT in result.references
    assert result.references[CONFIG_TYPE_SCRIPT][0].config_name == "Turn Off Lights"


async def test_scan_scene_references(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scanning finds scene references."""
    hass.states.async_set("light.bedroom", "off")
    hass.states.async_set(
        "scene.bedtime",
        "scening",
        {"friendly_name": "Bedtime Scene"},
    )

    mock_all_helpers["scenes"].return_value = ["scene.bedtime"]

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("light.bedroom")

    assert result.total_count == 1
    assert CONFIG_TYPE_SCENE in result.references
    assert result.references[CONFIG_TYPE_SCENE][0].config_name == "Bedtime Scene"


async def test_scan_group_references(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scanning finds group references."""
    hass.states.async_set("light.lamp_1", "on")
    hass.states.async_set(
        "group.all_lights",
        "on",
        {"friendly_name": "All Lights"},
    )

    mock_all_helpers["groups"].return_value = ["group.all_lights"]

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("light.lamp_1")

    assert result.total_count == 1
    assert CONFIG_TYPE_GROUP in result.references
    assert result.references[CONFIG_TYPE_GROUP][0].config_name == "All Lights"


async def test_scan_person_references(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scanning finds person device_tracker references."""
    hass.states.async_set("device_tracker.phone", "home")
    hass.states.async_set(
        "person.john",
        "home",
        {"friendly_name": "John"},
    )

    mock_all_helpers["persons"].return_value = ["person.john"]

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("device_tracker.phone")

    assert result.total_count == 1
    assert CONFIG_TYPE_PERSON in result.references
    assert result.references[CONFIG_TYPE_PERSON][0].config_name == "John"


async def test_scan_multiple_references(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scanning finds references across multiple config types."""
    hass.states.async_set("sensor.temperature", "21")
    hass.states.async_set(
        "automation.heating",
        "on",
        {"friendly_name": "Heating Control"},
    )
    hass.states.async_set(
        "script.temp_report",
        "off",
        {"friendly_name": "Temperature Report"},
    )

    mock_all_helpers["automations"].return_value = ["automation.heating"]
    mock_all_helpers["scripts"].return_value = ["script.temp_report"]

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("sensor.temperature")

    assert result.total_count == 2
    assert CONFIG_TYPE_AUTOMATION in result.references
    assert CONFIG_TYPE_SCRIPT in result.references


async def test_deep_scan_config_direct_match(hass: HomeAssistant) -> None:
    """Test deep scanning config for direct entity matches."""
    scanner = EntityMigrationScanner(hass)

    config = {"entity": "sensor.test"}
    found = scanner._deep_scan_config(config, "sensor.test")
    assert len(found) == 1
    assert "entity" in found[0]


async def test_deep_scan_config_nested_match(hass: HomeAssistant) -> None:
    """Test deep scanning config for nested entity matches."""
    scanner = EntityMigrationScanner(hass)

    config = {
        "views": [
            {
                "cards": [
                    {"type": "entity", "entity": "sensor.test"},
                ]
            }
        ]
    }
    found = scanner._deep_scan_config(config, "sensor.test")
    assert len(found) == 1
    assert "views[0].cards[0].entity" in found[0]


async def test_deep_scan_config_list_match(hass: HomeAssistant) -> None:
    """Test deep scanning config for entities in lists."""
    scanner = EntityMigrationScanner(hass)

    config = {"entities": ["sensor.test", "sensor.other"]}
    found = scanner._deep_scan_config(config, "sensor.test")
    assert len(found) == 1


async def test_deep_scan_config_template_match(hass: HomeAssistant) -> None:
    """Test deep scanning config for Jinja2 template references."""
    scanner = EntityMigrationScanner(hass)

    config = {"value_template": "{{ states('sensor.test') }}"}
    found = scanner._deep_scan_config(config, "sensor.test")
    assert len(found) == 1
    assert "(template)" in found[0]


async def test_deep_scan_config_is_state_template(hass: HomeAssistant) -> None:
    """Test deep scanning config for is_state template pattern."""
    scanner = EntityMigrationScanner(hass)

    config = {"value_template": "{{ is_state('sensor.test', 'on') }}"}
    found = scanner._deep_scan_config(config, "sensor.test")
    assert len(found) == 1


async def test_check_template_reference_states(hass: HomeAssistant) -> None:
    """Test template reference detection for states() function."""
    scanner = EntityMigrationScanner(hass)

    assert scanner._check_template_reference(
        "{{ states('sensor.temperature') }}", "sensor.temperature"
    )
    assert not scanner._check_template_reference(
        "{{ states('sensor.temperature') }}", "sensor.humidity"
    )


async def test_check_template_reference_is_state(hass: HomeAssistant) -> None:
    """Test template reference detection for is_state() function."""
    scanner = EntityMigrationScanner(hass)

    assert scanner._check_template_reference(
        "{% if is_state('sensor.door', 'open') %}", "sensor.door"
    )


async def test_check_template_reference_state_attr(hass: HomeAssistant) -> None:
    """Test template reference detection for state_attr() function."""
    scanner = EntityMigrationScanner(hass)

    assert scanner._check_template_reference(
        "{{ state_attr('climate.living_room', 'temperature') }}",
        "climate.living_room",
    )


async def test_scan_handles_missing_lovelace(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scan handles missing lovelace data gracefully."""
    hass.states.async_set("sensor.test", "on")

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("sensor.test")

    # Should complete without error even if lovelace isn't loaded
    assert result.source_entity_id == "sensor.test"


async def test_scan_result_as_dict(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test ScanResult serialization to dict."""
    hass.states.async_set("sensor.test", "on")
    hass.states.async_set(
        "automation.test",
        "on",
        {"friendly_name": "Test Automation"},
    )
    mock_all_helpers["automations"].return_value = ["automation.test"]

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("sensor.test")
    result_dict = result.as_dict()

    assert result_dict["source_entity_id"] == "sensor.test"
    assert "automation" in result_dict["references"]
    assert result_dict["total_count"] == 1
    assert result_dict["is_location_based"] is False


async def test_scan_graceful_error_handling(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scanner handles individual scan errors gracefully."""
    hass.states.async_set("sensor.test", "on")

    # Make one helper raise an exception
    mock_all_helpers["automations"].side_effect = Exception("Test error")

    scanner = EntityMigrationScanner(hass)
    result = await scanner.async_scan("sensor.test")

    # Should complete successfully, just skip the failing scan
    assert result.source_entity_id == "sensor.test"
    assert CONFIG_TYPE_AUTOMATION not in result.references
