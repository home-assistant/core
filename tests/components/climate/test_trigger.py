"""Test climate trigger."""

import pytest

from homeassistant.components import automation
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
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


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_climates(hass: HomeAssistant) -> None:
    """Create multiple climate entities associated with different targets."""
    await async_setup_component(hass, "climate", {})

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
    # Climate associated with area
    climate_area = entity_reg.async_get_or_create(
        domain="climate",
        platform="test",
        unique_id="climate_area",
        suggested_object_id="area_climate",
    )
    entity_reg.async_update_entity(climate_area.entity_id, area_id=area.id)

    # Climate associated with device
    entity_reg.async_get_or_create(
        domain="climate",
        platform="test",
        unique_id="climate_device",
        suggested_object_id="device_climate",
        device_id=device.id,
    )

    # Climate associated with label
    climate_label = entity_reg.async_get_or_create(
        domain="climate",
        platform="test",
        unique_id="climate_label",
        suggested_object_id="label_climate",
    )
    entity_reg.async_update_entity(climate_label.entity_id, labels={label.label_id})

    # Return all available climate entities
    return [
        "climate.standalone_climate",
        "climate.label_climate",
        "climate.area_climate",
        "climate.device_climate",
    ]


def set_or_remove_state(hass: HomeAssistant, entity_id: str, state: str | None) -> None:
    """Set or clear the state of an entity."""
    if state is None:
        hass.states.async_remove(entity_id)
    else:
        hass.states.async_set(entity_id, state, force_update=True)


async def setup_automation(
    hass: HomeAssistant, trigger: str, trigger_options: dict, trigger_target: dict
) -> None:
    """Set up automation component with given config."""
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: trigger,
                    CONF_OPTIONS: {**trigger_options},
                    CONF_TARGET: {**trigger_target},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "climates_in_target"),
    [
        (
            {CONF_ENTITY_ID: "climate.standalone_climate"},
            "climate.standalone_climate",
            1,
        ),
        ({ATTR_LABEL_ID: "test_label"}, "climate.label_climate", 2),
        ({ATTR_AREA_ID: "test_area"}, "climate.area_climate", 2),
        ({ATTR_FLOOR_ID: "test_floor"}, "climate.area_climate", 2),
        ({ATTR_LABEL_ID: "test_label"}, "climate.device_climate", 2),
        ({ATTR_AREA_ID: "test_area"}, "climate.device_climate", 2),
        ({ATTR_FLOOR_ID: "test_floor"}, "climate.device_climate", 2),
        ({ATTR_DEVICE_ID: "test_device"}, "climate.device_climate", 1),
    ],
)
@pytest.mark.parametrize(
    ("trigger", "initial_state", "states"),
    [
        # Initial state None
        (
            "climate.turned_off",
            None,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state opposite of target state
        (
            "climate.turned_off",
            HVACMode.HEAT,
            [(HVACMode.OFF, 1), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state same as target state
        (
            "climate.turned_off",
            HVACMode.OFF,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state unavailable / unknown
        (
            "climate.turned_off",
            STATE_UNAVAILABLE,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        (
            "climate.turned_off",
            STATE_UNKNOWN,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
    ],
)
async def test_climate_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entity_id: str,
    climates_in_target: int,
    trigger: str,
    initial_state: str,
    states: list[tuple[str, int]],
) -> None:
    """Test that the climate state trigger fires when any climate state changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, initial_state)
        await hass.async_block_till_done()

    await setup_automation(hass, trigger, {}, trigger_target_config)

    for state, expected_calls in states:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other climates also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == (climates_in_target - 1) * expected_calls
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id"),
    [
        ({CONF_ENTITY_ID: "climate.standalone_climate"}, "climate.standalone_climate"),
        ({ATTR_LABEL_ID: "test_label"}, "climate.label_climate"),
        ({ATTR_AREA_ID: "test_area"}, "climate.area_climate"),
        ({ATTR_FLOOR_ID: "test_floor"}, "climate.area_climate"),
        ({ATTR_LABEL_ID: "test_label"}, "climate.device_climate"),
        ({ATTR_AREA_ID: "test_area"}, "climate.device_climate"),
        ({ATTR_FLOOR_ID: "test_floor"}, "climate.device_climate"),
        ({ATTR_DEVICE_ID: "test_device"}, "climate.device_climate"),
    ],
)
@pytest.mark.parametrize(
    ("trigger", "initial_state", "states"),
    [
        # Initial state None
        (
            "climate.turned_off",
            None,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state opposite of target state
        (
            "climate.turned_off",
            HVACMode.HEAT,
            [(HVACMode.OFF, 1), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state same as target state
        (
            "climate.turned_off",
            HVACMode.OFF,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state unavailable / unknown
        (
            "climate.turned_off",
            STATE_UNAVAILABLE,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        (
            "climate.turned_off",
            STATE_UNKNOWN,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
    ],
)
async def test_climate_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entity_id: str,
    trigger: str,
    initial_state: str,
    states: list[tuple[str, int, list[str]]],
) -> None:
    """Test that the climate state trigger fires when the first climate changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, initial_state)
        await hass.async_block_till_done()

    await setup_automation(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state, expected_calls in states:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other climates should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id"),
    [
        ({CONF_ENTITY_ID: "climate.standalone_climate"}, "climate.standalone_climate"),
        ({ATTR_LABEL_ID: "test_label"}, "climate.label_climate"),
        ({ATTR_AREA_ID: "test_area"}, "climate.area_climate"),
        ({ATTR_FLOOR_ID: "test_floor"}, "climate.area_climate"),
        ({ATTR_LABEL_ID: "test_label"}, "climate.device_climate"),
        ({ATTR_AREA_ID: "test_area"}, "climate.device_climate"),
        ({ATTR_FLOOR_ID: "test_floor"}, "climate.device_climate"),
        ({ATTR_DEVICE_ID: "test_device"}, "climate.device_climate"),
    ],
)
@pytest.mark.parametrize(
    ("trigger", "initial_state", "states"),
    [
        # Initial state None
        (
            "climate.turned_off",
            None,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state opposite of target state
        (
            "climate.turned_off",
            HVACMode.HEAT,
            [(HVACMode.OFF, 1), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state same as target state
        (
            "climate.turned_off",
            HVACMode.OFF,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        # Initial state unavailable / unknown
        (
            "climate.turned_off",
            STATE_UNAVAILABLE,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
        (
            "climate.turned_off",
            STATE_UNKNOWN,
            [(HVACMode.OFF, 0), (HVACMode.HEAT, 0), (HVACMode.OFF, 1)],
        ),
    ],
)
async def test_climate_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entity_id: str,
    trigger: str,
    initial_state: str,
    states: list[tuple[str, int]],
) -> None:
    """Test that the climate state trigger fires when the last climate changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, initial_state)
        await hass.async_block_till_done()

    await setup_automation(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state, expected_calls in states:
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
