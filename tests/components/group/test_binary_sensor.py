"""The tests for the Group Binary Sensor platform."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.group import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_default_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test binary_sensor group default state."""
    hass.states.async_set("binary_sensor.kitchen", "on")
    hass.states.async_set("binary_sensor.bedroom", "on")
    await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["binary_sensor.kitchen", "binary_sensor.bedroom"],
                "name": "Bedroom Group",
                "unique_id": "unique_identifier",
                "device_class": "presence",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.bedroom_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "binary_sensor.bedroom",
        "binary_sensor.kitchen",
    ]

    entry = entity_registry.async_get("binary_sensor.bedroom_group")
    assert entry
    assert entry.unique_id == "unique_identifier"
    assert entry.original_name == "Bedroom Group"
    assert entry.original_device_class == "presence"


async def test_multiple_targets(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor from config entry with multiple targets."""
    hass.states.async_set("binary_sensor.kitchen", "on")
    hass.states.async_set("binary_sensor.bedroom", "on")

    group_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": {
                "area_id": ["bedroom"],
                "entity_id": [
                    "binary_sensor.kitchen",
                    "binary_sensor.bedroom",
                    "binary_sensor.not_exist",
                ],
                "label_id": ["test"],
            },
            "group_type": "binary_sensor",
            "name": "Bedroom Group",
            "all": False,
        },
        title="Bedroom Group",
        version=2,
    )
    group_config_entry.add_to_hass(hass)

    label_registry.async_create("Test")
    entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "in_a_label",
        suggested_object_id="in_a_label",
        config_entry=group_config_entry,
    )
    entity_registry.async_update_entity("binary_sensor.in_a_label", labels={"test"})
    hass.states.async_set("binary_sensor.in_a_label", "on")

    assert await hass.config_entries.async_setup(group_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.bedroom_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "binary_sensor.bedroom",
        "binary_sensor.in_a_label",
        "binary_sensor.kitchen",
        "binary_sensor.not_exist",
    ]

    entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "added_to_a_label",
        suggested_object_id="added_to_a_label",
        config_entry=group_config_entry,
    )
    entity_registry.async_update_entity(
        "binary_sensor.added_to_a_label", labels={"test"}
    )
    hass.states.async_set("binary_sensor.added_to_a_label", "on")

    entity_registry.async_get_or_create(
        "test",
        "test",
        "not_to_be_included",
        suggested_object_id="not_to_be_included",
        config_entry=group_config_entry,
    )
    entity_registry.async_update_entity("test.not_to_be_included", labels={"test"})
    hass.states.async_set("test.not_to_be_included", "on")

    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.bedroom_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "binary_sensor.added_to_a_label",
        "binary_sensor.bedroom",
        "binary_sensor.in_a_label",
        "binary_sensor.kitchen",
        "binary_sensor.not_exist",
    ]


async def test_state_reporting_all(hass: HomeAssistant) -> None:
    """Test the state reporting in 'all' mode.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if at least one group member
    is unknown or unavailable.
    Otherwise, the group state is off if at least one group member is
    off.
    Otherwise, the group state is on.
    """
    await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["binary_sensor.test1", "binary_sensor.test2"],
                "name": "Binary Sensor Group",
                "device_class": "presence",
                "all": "true",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert (
        hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNAVAILABLE
    )

    # All group members unavailable -> unavailable
    hass.states.async_set("binary_sensor.test1", STATE_UNAVAILABLE)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNAVAILABLE
    )

    # At least one member unknown or unavailable -> group unknown
    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNKNOWN

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNKNOWN

    hass.states.async_set("binary_sensor.test1", STATE_UNKNOWN)
    hass.states.async_set("binary_sensor.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNKNOWN

    hass.states.async_set("binary_sensor.test1", STATE_OFF)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNKNOWN

    hass.states.async_set("binary_sensor.test1", STATE_OFF)
    hass.states.async_set("binary_sensor.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNKNOWN

    hass.states.async_set("binary_sensor.test1", STATE_UNKNOWN)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNKNOWN

    # At least one member off -> group off
    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    hass.states.async_set("binary_sensor.test1", STATE_OFF)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    # Otherwise -> on
    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_ON

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("binary_sensor.test1")
    hass.states.async_remove("binary_sensor.test2")
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNAVAILABLE
    )


async def test_state_reporting_any(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the state reporting in 'any' mode.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if all group members are unknown.
    Otherwise, the group state is on if at least one group member is on.
    Otherwise, the group state is off.
    """
    await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["binary_sensor.test1", "binary_sensor.test2"],
                "name": "Binary Sensor Group",
                "device_class": "presence",
                "all": "false",
                "unique_id": "unique_identifier",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    entry = entity_registry.async_get("binary_sensor.binary_sensor_group")
    assert entry
    assert entry.unique_id == "unique_identifier"

    # Initial state with no group member in the state machine -> unavailable
    assert (
        hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNAVAILABLE
    )

    # All group members unavailable -> unavailable
    hass.states.async_set("binary_sensor.test1", STATE_UNAVAILABLE)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNAVAILABLE
    )

    # All group members unknown -> unknown
    hass.states.async_set("binary_sensor.test1", STATE_UNKNOWN)
    hass.states.async_set("binary_sensor.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNKNOWN

    # Group members unknown or unavailable -> unknown
    hass.states.async_set("binary_sensor.test1", STATE_UNKNOWN)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNKNOWN

    # At least one member on -> group on
    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_ON

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_ON

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_ON

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_ON

    # Otherwise -> off
    hass.states.async_set("binary_sensor.test1", STATE_OFF)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    hass.states.async_set("binary_sensor.test1", STATE_UNKNOWN)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    hass.states.async_set("binary_sensor.test1", STATE_UNAVAILABLE)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("binary_sensor.test1")
    hass.states.async_remove("binary_sensor.test2")
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNAVAILABLE
    )
