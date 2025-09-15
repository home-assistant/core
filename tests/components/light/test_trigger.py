"""Test light trigger."""

import pytest

from homeassistant.components import automation
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_device_registry

# remove when #151314 is merged
CONF_OPTIONS = "options"


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_lights(hass: HomeAssistant) -> None:
    """Create multiple light entities associated with different targets."""
    await async_setup_component(hass, "light", {})

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    floor_reg = fr.async_get(hass)
    floor = floor_reg.async_create("Test Floor")

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Test Area", floor_id=floor.floor_id)

    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Label")

    device = dr.DeviceEntry(id="test_device", area_id=area.id, labels={label.label_id})
    mock_device_registry(hass, {device.id: device})

    entity_reg = er.async_get(hass)
    # Light associated with area
    light_area = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="light_area",
        suggested_object_id="area_light",
    )
    entity_reg.async_update_entity(light_area.entity_id, area_id=area.id)

    # Light associated with device
    entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="light_device",
        suggested_object_id="device_light",
        device_id=device.id,
    )

    # Light associated with label
    light_label = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="light_label",
        suggested_object_id="label_light",
    )
    entity_reg.async_update_entity(light_label.entity_id, labels={label.label_id})

    # Return all available light entities
    return [
        "light.standalone_light",
        "light.label_light",
        "light.area_light",
        "light.device_light",
    ]


@pytest.mark.usefixtures("target_lights")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id"),
    [
        ({CONF_ENTITY_ID: "light.standalone_light"}, "light.standalone_light"),
        ({ATTR_LABEL_ID: "test_label"}, "light.label_light"),
        ({ATTR_AREA_ID: "test_area"}, "light.area_light"),
        ({ATTR_FLOOR_ID: "test_floor"}, "light.area_light"),
        ({ATTR_LABEL_ID: "test_label"}, "light.device_light"),
        ({ATTR_AREA_ID: "test_area"}, "light.device_light"),
        ({ATTR_FLOOR_ID: "test_floor"}, "light.device_light"),
        ({ATTR_DEVICE_ID: "test_device"}, "light.device_light"),
    ],
)
@pytest.mark.parametrize(
    ("state", "reverse_state"), [(STATE_ON, STATE_OFF), (STATE_OFF, STATE_ON)]
)
async def test_light_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_target_config: dict,
    entity_id: str,
    state: str,
    reverse_state: str,
) -> None:
    """Test that the light state trigger fires when any light state changes to a specific state."""
    await async_setup_component(hass, "light", {})

    hass.states.async_set(entity_id, reverse_state)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "light.state",
                    CONF_TARGET: {**trigger_target_config},
                    CONF_OPTIONS: {CONF_STATE: state},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: f"{entity_id}"},
                },
            }
        },
    )

    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    hass.states.async_set(entity_id, reverse_state)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id"),
    [
        ({CONF_ENTITY_ID: "light.standalone_light"}, "light.standalone_light"),
        ({ATTR_LABEL_ID: "test_label"}, "light.label_light"),
        ({ATTR_AREA_ID: "test_area"}, "light.area_light"),
        ({ATTR_FLOOR_ID: "test_floor"}, "light.area_light"),
        ({ATTR_LABEL_ID: "test_label"}, "light.device_light"),
        ({ATTR_AREA_ID: "test_area"}, "light.device_light"),
        ({ATTR_FLOOR_ID: "test_floor"}, "light.device_light"),
        ({ATTR_DEVICE_ID: "test_device"}, "light.device_light"),
    ],
)
@pytest.mark.parametrize(
    ("state", "reverse_state"), [(STATE_ON, STATE_OFF), (STATE_OFF, STATE_ON)]
)
async def test_light_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: list[str],
    trigger_target_config: dict,
    entity_id: str,
    state: str,
    reverse_state: str,
) -> None:
    """Test that the light state trigger fires when the first light changes to a specific state."""
    await async_setup_component(hass, "light", {})

    for other_entity_id in target_lights:
        hass.states.async_set(other_entity_id, reverse_state)
        await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "light.state",
                    CONF_TARGET: {**trigger_target_config},
                    CONF_OPTIONS: {CONF_STATE: state, "behavior": "first"},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: f"{entity_id}"},
                },
            }
        },
    )
    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Triggering other lights should not cause any service calls after the first one
    for other_entity_id in target_lights:
        hass.states.async_set(other_entity_id, state)
        await hass.async_block_till_done()
    for other_entity_id in target_lights:
        hass.states.async_set(other_entity_id, reverse_state)
        await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id"),
    [
        ({CONF_ENTITY_ID: "light.standalone_light"}, "light.standalone_light"),
        ({ATTR_LABEL_ID: "test_label"}, "light.label_light"),
        ({ATTR_AREA_ID: "test_area"}, "light.area_light"),
        ({ATTR_FLOOR_ID: "test_floor"}, "light.area_light"),
        ({ATTR_LABEL_ID: "test_label"}, "light.device_light"),
        ({ATTR_AREA_ID: "test_area"}, "light.device_light"),
        ({ATTR_FLOOR_ID: "test_floor"}, "light.device_light"),
        ({ATTR_DEVICE_ID: "test_device"}, "light.device_light"),
    ],
)
@pytest.mark.parametrize(
    ("state", "reverse_state"), [(STATE_ON, STATE_OFF), (STATE_OFF, STATE_ON)]
)
async def test_light_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: list[str],
    trigger_target_config: dict,
    entity_id: str,
    state: str,
    reverse_state: str,
) -> None:
    """Test that the light state trigger fires when the last light changes to a specific state."""
    await async_setup_component(hass, "light", {})

    for other_entity_id in target_lights:
        hass.states.async_set(other_entity_id, reverse_state)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "light.state",
                    CONF_TARGET: {**trigger_target_config},
                    CONF_OPTIONS: {CONF_STATE: state, "behavior": "last"},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: f"{entity_id}"},
                },
            }
        },
    )

    target_lights.remove(entity_id)
    for other_entity_id in target_lights:
        hass.states.async_set(other_entity_id, state)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
