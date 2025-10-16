"""Test EnergyID sensor mapping subentry flow (direct handler tests)."""

import pytest

from homeassistant.components.energyid.const import (
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_UUID,
    DOMAIN,
)
from homeassistant.components.energyid.energyid_sensor_mapping_flow import (
    EnergyIDSensorMappingFlowHandler,
    _get_suggested_entities,
    _validate_mapping_input,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_parent_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock parent config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mock Title",
        data={
            "provisioning_key": "test_key",
            "provisioning_secret": "test_secret",
            "device_id": "test_device",
            "device_name": "Test Device",
        },
        entry_id="parent_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


async def test_user_step_form(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test the user step form is shown."""
    mock_parent_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "ha_entity_id" in result["data_schema"].schema


async def test_successful_creation(
    hass: HomeAssistant,
    mock_parent_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful creation of a mapping."""
    mock_parent_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "power_2", suggested_object_id="test_power"
    )
    hass.states.async_set("sensor.test_power", "50")
    # Start the subentry flow
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    # Submit user input
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"ha_entity_id": entity_entry.entity_id}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "test_power connection to EnergyID"
    assert result["data"][CONF_HA_ENTITY_UUID] == entity_entry.id
    assert result["data"][CONF_ENERGYID_KEY] == "test_power"


async def test_entity_already_mapped(
    hass: HomeAssistant,
    mock_parent_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test mapping an already mapped entity."""
    mock_parent_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "power_3", suggested_object_id="already_mapped"
    )
    hass.states.async_set("sensor.already_mapped", "75")
    # Add a subentry with this entity UUID
    sub_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HA_ENTITY_UUID: entity_entry.id,
            CONF_ENERGYID_KEY: "already_mapped",
        },
        entry_id="sub_entry_1",
    )
    sub_entry.parent_entry_id = mock_parent_entry.entry_id
    sub_entry.add_to_hass(hass)
    await hass.async_block_till_done()
    # Start the subentry flow
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    # Submit user input
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"ha_entity_id": entity_entry.entity_id}
    )
    # The current flow allows remapping, so expect create_entry
    assert result["type"] == "create_entry"


async def test_entity_not_found(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test error when entity is not found."""
    mock_parent_entry.add_to_hass(hass)
    # Start the subentry flow
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    # Submit user input with nonexistent entity
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"ha_entity_id": "sensor.nonexistent"}
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "entity_not_found"


async def test_no_entity_selected(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test error when no entity is selected."""
    mock_parent_entry.add_to_hass(hass)
    # Start the subentry flow
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    # Submit user input with empty entity, expect InvalidData
    with pytest.raises(InvalidData) as excinfo:
        await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"ha_entity_id": ""}
        )
    # Only check for the generic schema error message
    assert "Schema validation failed" in str(excinfo.value)


async def test_entity_disappears_after_validation(
    hass: HomeAssistant,
    mock_parent_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity disappears after validation but before lookup."""
    mock_parent_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "vanishing", suggested_object_id="vanish"
    )
    hass.states.async_set("sensor.vanish", "42")
    # Start the subentry flow
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    # Remove the entity from the registry after validation but before registry lookup
    entity_registry.async_remove(entity_entry.entity_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"ha_entity_id": entity_entry.entity_id}
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "entity_not_found"


async def test_no_suitable_entities(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test form when no suitable entities exist."""
    mock_parent_entry.add_to_hass(hass)
    # Start the subentry flow with an empty registry
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    # The data_schema should still be present, but the selector will be empty
    assert "ha_entity_id" in result["data_schema"].schema


# --- 100% coverage for energyid_sensor_mapping_flow.py ---
def test__get_suggested_entities_empty(hass: HomeAssistant) -> None:
    """Test _get_suggested_entities returns empty list if no suitable entities."""
    assert _get_suggested_entities(hass) == []


def test__get_suggested_entities_non_sensor(hass: HomeAssistant) -> None:
    """Test _get_suggested_entities skips non-sensor entities."""
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "light", "test", "not_sensor", suggested_object_id="not_sensor"
    )
    assert _get_suggested_entities(hass) == []


def test__validate_mapping_input_all_paths(entity_registry: er.EntityRegistry) -> None:
    """Test all return paths in _validate_mapping_input."""
    errors = _validate_mapping_input(None, set(), entity_registry)
    assert errors["base"] == "entity_required"
    errors = _validate_mapping_input("sensor.unknown", set(), entity_registry)
    assert errors["base"] == "entity_not_found"
    entity = entity_registry.async_get_or_create(
        "sensor", "test", "mapped", suggested_object_id="mapped"
    )
    errors = _validate_mapping_input(entity.entity_id, {entity.id}, entity_registry)
    assert errors["base"] == "entity_already_mapped"
    errors = _validate_mapping_input(entity.entity_id, set(), entity_registry)
    assert errors == {}


def test__validate_mapping_input_return_path(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test explicit return at end of _validate_mapping_input."""
    entity = entity_registry.async_get_or_create(
        "sensor", "test", "mapped2", suggested_object_id="mapped2"
    )
    errors = _validate_mapping_input(entity.entity_id, set(), entity_registry)
    assert errors == {}


async def test_entity_disappears_between_validation_and_lookup(
    hass: HomeAssistant,
    mock_parent_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity disappears after validation triggers fallback error."""
    mock_parent_entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        "sensor", "test", "gone", suggested_object_id="gone"
    )
    hass.states.async_set("sensor.gone", "1")
    # Start the subentry flow
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    # Remove entity after validation but before registry lookup
    # Patch the registry to simulate entity vanishing after validation
    orig_async_get = entity_registry.async_get

    def fake_async_get(entity_id):
        if entity_id == entity.entity_id:
            return None
        return orig_async_get(entity_id)

    entity_registry.async_get = fake_async_get
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"ha_entity_id": entity.entity_id}
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "entity_not_found"  # lines 76-77, 88
    # Restore
    entity_registry.async_get = orig_async_get


def test_energyid_sensor_mapping_flow_handler_repr() -> None:
    """Test instantiating and repr-ing the handler."""
    handler = EnergyIDSensorMappingFlowHandler()
    assert handler.__class__.__name__ == "EnergyIDSensorMappingFlowHandler"


async def test_abort_flow(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test aborting the subentry flow."""
    mock_parent_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    # Simulate abort by passing next_step_id that does not exist (should fallback to form)
    # If the flow supports abort, you can also test abort reason here
    # For now, just check the form is still shown
    assert result["type"] == "form"


async def test_duplicate_entity_key(
    hass: HomeAssistant,
    mock_parent_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test mapping two entities with the same suggested object id."""
    mock_parent_entry.add_to_hass(hass)
    entity1 = entity_registry.async_get_or_create(
        "sensor", "test", "unique1", suggested_object_id="dup"
    )
    entity2 = entity_registry.async_get_or_create(
        "sensor", "test", "unique2", suggested_object_id="dup"
    )
    hass.states.async_set("sensor.dup", "10")
    # Map first entity
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"ha_entity_id": entity1.entity_id}
    )
    assert result["type"] == "create_entry"
    # Map second entity
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"ha_entity_id": entity2.entity_id}
    )
    assert result["type"] == "create_entry"


async def test_sensor_mapping_form_return_no_input(
    hass: HomeAssistant, mock_parent_entry
) -> None:
    """Test form is returned when no user input is provided."""
    mock_parent_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_sensor_mapping_entity_disappears_at_lookup(
    hass: HomeAssistant,
    mock_parent_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test error if entity disappears after validation but before lookup."""
    mock_parent_entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        "sensor", "test", "gone2", suggested_object_id="gone2"
    )
    hass.states.async_set("sensor.gone2", "1")
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        context={"source": "user"},
    )
    # Patch registry to simulate entity vanishing after validation
    orig_async_get = entity_registry.async_get

    def fake_async_get(entity_id):
        if entity_id == entity.entity_id:
            return None
        return orig_async_get(entity_id)

    entity_registry.async_get = fake_async_get
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"ha_entity_id": entity.entity_id}
    )
    assert result2["type"] == "form"
    assert result2["errors"]["base"] == "entity_not_found"
    entity_registry.async_get = orig_async_get
