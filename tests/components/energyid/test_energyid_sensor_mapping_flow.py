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


@pytest.mark.parametrize(
    ("entities_to_create"),
    [
        ([]),  # empty case
        ([("light", "test", "not_sensor", "not_sensor")]),  # non-sensor case
    ],
)
def test_get_suggested_entities_no_suitable_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entities_to_create: list[tuple[str, str, str, str]],
) -> None:
    """Test _get_suggested_entities returns empty list if no suitable entities."""
    for domain, platform, unique_id, suggested_object_id in entities_to_create:
        entity_registry.async_get_or_create(
            domain, platform, unique_id, suggested_object_id=suggested_object_id
        )
    assert _get_suggested_entities(hass) == []


def test_energyid_sensor_mapping_flow_handler_repr() -> None:
    """Test instantiating and repr-ing the handler."""
    handler = EnergyIDSensorMappingFlowHandler()
    assert handler.__class__.__name__ == "EnergyIDSensorMappingFlowHandler"


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
