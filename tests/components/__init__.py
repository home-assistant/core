"""The tests for components."""

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_device_registry


async def target_entities(hass: HomeAssistant, domain: str) -> None:
    """Create multiple entities associated with different targets."""
    await async_setup_component(hass, domain, {})

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
    # Entity associated with area
    entity_area = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_area",
        suggested_object_id=f"area_{domain}",
    )
    entity_reg.async_update_entity(entity_area.entity_id, area_id=area.id)

    # Entity associated with device
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device",
        suggested_object_id=f"device_{domain}",
        device_id=device.id,
    )

    # Entity associated with label
    entity_label = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_label",
        suggested_object_id=f"label_{domain}",
    )
    entity_reg.async_update_entity(entity_label.entity_id, labels={label.label_id})

    # Return all available entities
    return [
        f"{domain}.standalone_{domain}",
        f"{domain}.label_{domain}",
        f"{domain}.area_{domain}",
        f"{domain}.device_{domain}",
    ]


def parametrize_target_entities(domain: str) -> list[tuple[dict, str, int]]:
    """Parametrize target entities for different target types.

    Meant to be used with target_entities.
    """
    return [
        (
            {CONF_ENTITY_ID: f"{domain}.standalone_{domain}"},
            f"{domain}.standalone_{domain}",
            1,
        ),
        ({ATTR_LABEL_ID: "test_label"}, f"{domain}.label_{domain}", 2),
        ({ATTR_AREA_ID: "test_area"}, f"{domain}.area_{domain}", 2),
        ({ATTR_FLOOR_ID: "test_floor"}, f"{domain}.area_{domain}", 2),
        ({ATTR_LABEL_ID: "test_label"}, f"{domain}.device_{domain}", 2),
        ({ATTR_AREA_ID: "test_area"}, f"{domain}.device_{domain}", 2),
        ({ATTR_FLOOR_ID: "test_floor"}, f"{domain}.device_{domain}", 2),
        ({ATTR_DEVICE_ID: "test_device"}, f"{domain}.device_{domain}", 1),
    ]


def parametrize_trigger_states(
    trigger: str, target_state: str, other_state: str
) -> tuple[str, list[tuple[str, int]]]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, initial_state, list of states),
    where states is a list of tuples (state to set, expected service call count).
    """
    return [
        # Initial state None
        (
            trigger,
            None,
            [(target_state, 0), (other_state, 0), (target_state, 1)],
        ),
        # Initial state different from target state
        (
            trigger,
            other_state,
            [(target_state, 1), (other_state, 0), (target_state, 1)],
        ),
        # Initial state same as target state
        (
            trigger,
            target_state,
            [(target_state, 0), (other_state, 0), (target_state, 1)],
        ),
        # Initial state unavailable / unknown
        (
            trigger,
            STATE_UNAVAILABLE,
            [(target_state, 0), (other_state, 0), (target_state, 1)],
        ),
        (
            trigger,
            STATE_UNKNOWN,
            [(target_state, 0), (other_state, 0), (target_state, 1)],
        ),
    ]
