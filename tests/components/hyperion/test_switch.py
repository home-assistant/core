"""Tests for the Hyperion integration."""
from datetime import timedelta
from unittest.mock import AsyncMock, call, patch

from hyperion.const import (
    KEY_COMPONENT,
    KEY_COMPONENTID_ALL,
    KEY_COMPONENTID_TO_NAME,
    KEY_COMPONENTSTATE,
    KEY_STATE,
)

from homeassistant.components.hyperion import get_hyperion_device_id
from homeassistant.components.hyperion.const import (
    DOMAIN,
    HYPERION_MANUFACTURER_NAME,
    HYPERION_MODEL_NAME,
    TYPE_HYPERION_COMPONENT_SWITCH_BASE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt, slugify

from . import (
    TEST_CONFIG_ENTRY_ID,
    TEST_INSTANCE,
    TEST_INSTANCE_1,
    TEST_SYSINFO_ID,
    call_registered_callback,
    create_mock_client,
    register_test_entity,
    setup_test_config_entry,
)

from tests.common import async_fire_time_changed

TEST_COMPONENTS = [
    {"enabled": True, "name": "ALL"},
    {"enabled": True, "name": "SMOOTHING"},
    {"enabled": True, "name": "BLACKBORDER"},
    {"enabled": False, "name": "FORWARDER"},
    {"enabled": False, "name": "BOBLIGHTSERVER"},
    {"enabled": False, "name": "GRABBER"},
    {"enabled": False, "name": "V4L"},
    {"enabled": True, "name": "LEDDEVICE"},
]

TEST_SWITCH_COMPONENT_BASE_ENTITY_ID = "switch.test_instance_1_component"
TEST_SWITCH_COMPONENT_ALL_ENTITY_ID = f"{TEST_SWITCH_COMPONENT_BASE_ENTITY_ID}_all"


async def test_switch_turn_on_off(hass: HomeAssistant) -> None:
    """Test turning the light on."""
    client = create_mock_client()
    client.async_send_set_component = AsyncMock(return_value=True)
    client.components = TEST_COMPONENTS

    # Setup component switch.
    register_test_entity(
        hass,
        SWITCH_DOMAIN,
        f"{TYPE_HYPERION_COMPONENT_SWITCH_BASE}_all",
        TEST_SWITCH_COMPONENT_ALL_ENTITY_ID,
    )
    await setup_test_config_entry(hass, hyperion_client=client)

    # Verify switch is on (as per TEST_COMPONENTS above).
    entity_state = hass.states.get(TEST_SWITCH_COMPONENT_ALL_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"

    # Turn switch off.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_SWITCH_COMPONENT_ALL_ENTITY_ID},
        blocking=True,
    )

    # Verify correct parameters are passed to the library.
    assert client.async_send_set_component.call_args == call(
        **{KEY_COMPONENTSTATE: {KEY_COMPONENT: KEY_COMPONENTID_ALL, KEY_STATE: False}}
    )

    client.components[0] = {
        "enabled": False,
        "name": "ALL",
    }
    call_registered_callback(client, "components-update")

    # Verify the switch turns off.
    entity_state = hass.states.get(TEST_SWITCH_COMPONENT_ALL_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    # Turn switch on.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SWITCH_COMPONENT_ALL_ENTITY_ID},
        blocking=True,
    )

    # Verify correct parameters are passed to the library.
    assert client.async_send_set_component.call_args == call(
        **{KEY_COMPONENTSTATE: {KEY_COMPONENT: KEY_COMPONENTID_ALL, KEY_STATE: True}}
    )

    client.components[0] = {
        "enabled": True,
        "name": "ALL",
    }
    call_registered_callback(client, "components-update")

    # Verify the switch turns on.
    entity_state = hass.states.get(TEST_SWITCH_COMPONENT_ALL_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"


async def test_switch_has_correct_entities(hass: HomeAssistant) -> None:
    """Test that the correct switch entities are created."""
    client = create_mock_client()
    client.components = TEST_COMPONENTS

    # Setup component switch.
    for component in TEST_COMPONENTS:
        name = slugify(KEY_COMPONENTID_TO_NAME[str(component["name"])])
        register_test_entity(
            hass,
            SWITCH_DOMAIN,
            f"{TYPE_HYPERION_COMPONENT_SWITCH_BASE}_{name}",
            f"{TEST_SWITCH_COMPONENT_BASE_ENTITY_ID}_{name}",
        )
    await setup_test_config_entry(hass, hyperion_client=client)

    for component in TEST_COMPONENTS:
        name = slugify(KEY_COMPONENTID_TO_NAME[str(component["name"])])
        entity_id = TEST_SWITCH_COMPONENT_BASE_ENTITY_ID + "_" + name
        entity_state = hass.states.get(entity_id)
        assert entity_state, f"Couldn't find entity: {entity_id}"


async def test_device_info(hass: HomeAssistant) -> None:
    """Verify device information includes expected details."""
    client = create_mock_client()
    client.components = TEST_COMPONENTS

    for component in TEST_COMPONENTS:
        name = slugify(KEY_COMPONENTID_TO_NAME[str(component["name"])])
        register_test_entity(
            hass,
            SWITCH_DOMAIN,
            f"{TYPE_HYPERION_COMPONENT_SWITCH_BASE}_{name}",
            f"{TEST_SWITCH_COMPONENT_BASE_ENTITY_ID}_{name}",
        )

    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_SWITCH_COMPONENT_ALL_ENTITY_ID) is not None

    device_identifer = get_hyperion_device_id(TEST_SYSINFO_ID, TEST_INSTANCE)
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_device({(DOMAIN, device_identifer)})
    assert device
    assert device.config_entries == {TEST_CONFIG_ENTRY_ID}
    assert device.identifiers == {(DOMAIN, device_identifer)}
    assert device.manufacturer == HYPERION_MANUFACTURER_NAME
    assert device.model == HYPERION_MODEL_NAME
    assert device.name == TEST_INSTANCE_1["friendly_name"]

    entity_registry = await er.async_get_registry(hass)
    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]

    for component in TEST_COMPONENTS:
        name = slugify(KEY_COMPONENTID_TO_NAME[str(component["name"])])
        entity_id = TEST_SWITCH_COMPONENT_BASE_ENTITY_ID + "_" + name
        assert entity_id in entities_from_device


async def test_switches_can_be_enabled(hass: HomeAssistant) -> None:
    """Verify switches can be enabled."""
    client = create_mock_client()
    client.components = TEST_COMPONENTS
    await setup_test_config_entry(hass, hyperion_client=client)

    entity_registry = er.async_get(hass)

    for component in TEST_COMPONENTS:
        name = slugify(KEY_COMPONENTID_TO_NAME[str(component["name"])])
        entity_id = TEST_SWITCH_COMPONENT_BASE_ENTITY_ID + "_" + name

        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.disabled
        assert entry.disabled_by == "integration"
        entity_state = hass.states.get(entity_id)
        assert not entity_state

        with patch(
            "homeassistant.components.hyperion.client.HyperionClient",
            return_value=client,
        ):
            updated_entry = entity_registry.async_update_entity(
                entity_id, disabled_by=None
            )
            assert not updated_entry.disabled
            await hass.async_block_till_done()

            async_fire_time_changed(  # type: ignore[no-untyped-call]
                hass,
                dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
            )
            await hass.async_block_till_done()

        entity_state = hass.states.get(entity_id)
        assert entity_state
