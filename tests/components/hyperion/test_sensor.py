"""Tests for the Hyperion integration."""

from hyperion.const import (
    KEY_ACTIVE,
    KEY_COMPONENTID,
    KEY_ORIGIN,
    KEY_OWNER,
    KEY_PRIORITY,
    KEY_RGB,
    KEY_VALUE,
    KEY_VISIBLE,
)

from homeassistant.components.hyperion import get_hyperion_device_id
from homeassistant.components.hyperion.const import (
    DOMAIN,
    HYPERION_MANUFACTURER_NAME,
    HYPERION_MODEL_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from . import (
    TEST_CONFIG_ENTRY_ID,
    TEST_INSTANCE,
    TEST_INSTANCE_1,
    TEST_SYSINFO_ID,
    call_registered_callback,
    create_mock_client,
    setup_test_config_entry,
)

TEST_COMPONENTS = [
    {"enabled": True, "name": "VISIBLE_PRIORITY"},
]

TEST_SENSOR_BASE_ENTITY_ID = "sensor.test_instance_1"
TEST_VISIBLE_EFFECT_SENSOR_ID = "sensor.test_instance_1_visible_priority"


async def test_sensor_has_correct_entities(hass: HomeAssistant) -> None:
    """Test that the correct sensor entities are created."""
    client = create_mock_client()
    client.components = TEST_COMPONENTS
    await setup_test_config_entry(hass, hyperion_client=client)

    for component in TEST_COMPONENTS:
        name = slugify(component["name"])
        entity_id = f"{TEST_SENSOR_BASE_ENTITY_ID}_{name}"
        entity_state = hass.states.get(entity_id)
        assert entity_state, f"Couldn't find entity: {entity_id}"


async def test_device_info(hass: HomeAssistant) -> None:
    """Verify device information includes expected details."""
    client = create_mock_client()
    client.components = TEST_COMPONENTS
    await setup_test_config_entry(hass, hyperion_client=client)

    device_identifer = get_hyperion_device_id(TEST_SYSINFO_ID, TEST_INSTANCE)
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_identifer)})
    assert device
    assert device.config_entries == {TEST_CONFIG_ENTRY_ID}
    assert device.identifiers == {(DOMAIN, device_identifer)}
    assert device.manufacturer == HYPERION_MANUFACTURER_NAME
    assert device.model == HYPERION_MODEL_NAME
    assert device.name == TEST_INSTANCE_1["friendly_name"]

    entity_registry = er.async_get(hass)
    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]

    for component in TEST_COMPONENTS:
        name = slugify(component["name"])
        entity_id = TEST_SENSOR_BASE_ENTITY_ID + "_" + name
        assert entity_id in entities_from_device


async def test_visible_effect_state_changes(hass: HomeAssistant) -> None:
    """Verify that state changes are processed as expected for visible effect sensor."""
    client = create_mock_client()
    client.components = TEST_COMPONENTS
    await setup_test_config_entry(hass, hyperion_client=client)

    # Simulate a platform grabber effect state callback from Hyperion.
    client.priorities = [
        {
            KEY_ACTIVE: True,
            KEY_COMPONENTID: "GRABBER",
            KEY_ORIGIN: "System",
            KEY_OWNER: "X11",
            KEY_PRIORITY: 250,
            KEY_VISIBLE: True,
        }
    ]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_VISIBLE_EFFECT_SENSOR_ID)
    assert entity_state
    assert entity_state.state == client.priorities[0][KEY_OWNER]
    assert (
        entity_state.attributes["component_id"] == client.priorities[0][KEY_COMPONENTID]
    )
    assert entity_state.attributes["origin"] == client.priorities[0][KEY_ORIGIN]
    assert entity_state.attributes["priority"] == client.priorities[0][KEY_PRIORITY]

    # Simulate an effect state callback from Hyperion.
    client.priorities = [
        {
            KEY_ACTIVE: True,
            KEY_COMPONENTID: "EFFECT",
            KEY_ORIGIN: "System",
            KEY_OWNER: "Warm mood blobs",
            KEY_PRIORITY: 250,
            KEY_VISIBLE: True,
        }
    ]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_VISIBLE_EFFECT_SENSOR_ID)
    assert entity_state
    assert entity_state.state == client.priorities[0][KEY_OWNER]
    assert (
        entity_state.attributes["component_id"] == client.priorities[0][KEY_COMPONENTID]
    )
    assert entity_state.attributes["origin"] == client.priorities[0][KEY_ORIGIN]
    assert entity_state.attributes["priority"] == client.priorities[0][KEY_PRIORITY]

    # Simulate a USB Capture state callback from Hyperion.
    client.priorities = [
        {
            KEY_ACTIVE: True,
            KEY_COMPONENTID: "V4L",
            KEY_ORIGIN: "System",
            KEY_OWNER: "V4L2",
            KEY_PRIORITY: 250,
            KEY_VISIBLE: True,
        }
    ]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_VISIBLE_EFFECT_SENSOR_ID)
    assert entity_state
    assert entity_state.state == client.priorities[0][KEY_OWNER]
    assert (
        entity_state.attributes["component_id"] == client.priorities[0][KEY_COMPONENTID]
    )
    assert entity_state.attributes["origin"] == client.priorities[0][KEY_ORIGIN]
    assert entity_state.attributes["priority"] == client.priorities[0][KEY_PRIORITY]

    # Simulate a color effect state callback from Hyperion.
    client.priorities = [
        {
            KEY_ACTIVE: True,
            KEY_COMPONENTID: "COLOR",
            KEY_ORIGIN: "System",
            KEY_PRIORITY: 250,
            KEY_VALUE: {KEY_RGB: [0, 0, 0]},
            KEY_VISIBLE: True,
        }
    ]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_VISIBLE_EFFECT_SENSOR_ID)
    assert entity_state
    assert entity_state.state == str(client.priorities[0][KEY_VALUE][KEY_RGB])
    assert (
        entity_state.attributes["component_id"] == client.priorities[0][KEY_COMPONENTID]
    )
    assert entity_state.attributes["origin"] == client.priorities[0][KEY_ORIGIN]
    assert entity_state.attributes["priority"] == client.priorities[0][KEY_PRIORITY]
    assert entity_state.attributes["color"] == client.priorities[0][KEY_VALUE]
