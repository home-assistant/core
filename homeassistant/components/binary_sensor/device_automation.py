"""Provides device automations for lights."""
import voluptuous as vol

import homeassistant.components.automation.state as state
from homeassistant.components.device_automation.const import (
    CONF_IS_OFF,
    CONF_IS_ON,
    CONF_TURNED_OFF,
    CONF_TURNED_ON,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import split_entity_id
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers import condition, config_validation as cv

from . import (
    DOMAIN,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_COLD,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_LIGHT,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_MOVING,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESENCE,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_SOUND,
    DEVICE_CLASS_VIBRATION,
    DEVICE_CLASS_WINDOW,
)


# mypy: allow-untyped-defs, no-check-untyped-defs

DEVICE_CLASS_NONE = "none"

CONF_IS_BAT_LOW = "is_bat_low"
CONF_IS_NOT_BAT_LOW = "is_not_bat_low"
CONF_IS_COLD = "is_cold"
CONF_IS_NOT_COLD = "is_not_cold"
CONF_IS_CONNECTED = "is_connected"
CONF_IS_NOT_CONNECTED = "is_not_connected"
CONF_IS_GAS = "is_gas"
CONF_IS_NO_GAS = "is_no_gas"
CONF_IS_HOT = "is_hot"
CONF_IS_NOT_HOT = "is_not_hot"
CONF_IS_LIGHT = "is_light"
CONF_IS_NO_LIGHT = "is_no_light"
CONF_IS_LOCKED = "is_locked"
CONF_IS_NOT_LOCKED = "is_not_locked"
CONF_IS_MOIST = "is_moist"
CONF_IS_NOT_MOIST = "is_not_moist"
CONF_IS_MOTION = "is_motion"
CONF_IS_NO_MOTION = "is_no_motion"
CONF_IS_MOVING = "is_moving"
CONF_IS_NOT_MOVING = "is_not_moving"
CONF_IS_OCCUPIED = "is_occupied"
CONF_IS_NOT_OCCUPIED = "is_not_occupied"
CONF_IS_PLUGGED_IN = "is_plugged_in"
CONF_IS_NOT_PLUGGED_IN = "is_not_plugged_in"
CONF_IS_POWERED = "is_powered"
CONF_IS_NOT_POWERED = "is_not_powered"
CONF_IS_PRESENT = "is_present"
CONF_IS_NOT_PRESENT = "is_not_present"
CONF_IS_PROBLEM = "is_problem"
CONF_IS_NO_PROBLEM = "is_no_problem"
CONF_IS_UNSAFE = "is_unsafe"
CONF_IS_NOT_UNSAFE = "is_not_unsafe"
CONF_IS_SMOKE = "is_smoke"
CONF_IS_NO_SMOKE = "is_no_smoke"
CONF_IS_SOUND = "is_sound"
CONF_IS_NO_SOUND = "is_no_sound"
CONF_IS_VIBRATION = "is_vibration"
CONF_IS_NO_VIBRATION = "is_no_vibration"
CONF_IS_OPEN = "is_open"
CONF_IS_NOT_OPEN = "is_not_open"

CONF_BAT_LOW = "bat_low"
CONF_NOT_BAT_LOW = "not_bat_low"
CONF_COLD = "cold"
CONF_NOT_COLD = "not_cold"
CONF_CONNECTED = "connected"
CONF_NOT_CONNECTED = "not_connected"
CONF_GAS = "gas"
CONF_NO_GAS = "no_gas"
CONF_HOT = "hot"
CONF_NOT_HOT = "not_hot"
CONF_LIGHT = "light"
CONF_NO_LIGHT = "no_light"
CONF_LOCKED = "locked"
CONF_NOT_LOCKED = "not_locked"
CONF_MOIST = "moist"
CONF_NOT_MOIST = "not_moist"
CONF_MOTION = "motion"
CONF_NO_MOTION = "no_motion"
CONF_MOVING = "moving"
CONF_NOT_MOVING = "not_moving"
CONF_OCCUPIED = "occupied"
CONF_NOT_OCCUPIED = "not_occupied"
CONF_PLUGGED_IN = "plugged_in"
CONF_NOT_PLUGGED_IN = "not_plugged_in"
CONF_POWERED = "powered"
CONF_NOT_POWERED = "not_powered"
CONF_PRESENT = "present"
CONF_NOT_PRESENT = "not_present"
CONF_PROBLEM = "problem"
CONF_NO_PROBLEM = "no_problem"
CONF_UNSAFE = "unsafe"
CONF_NOT_UNSAFE = "not_unsafe"
CONF_SMOKE = "smoke"
CONF_NO_SMOKE = "no_smoke"
CONF_SOUND = "sound"
CONF_NO_SOUND = "no_sound"
CONF_VIBRATION = "vibration"
CONF_NO_VIBRATION = "no_vibration"
CONF_OPEN = "open"
CONF_NOT_OPEN = "not_open"

IS_ON = [
    CONF_IS_BAT_LOW,
    CONF_IS_COLD,
    CONF_IS_CONNECTED,
    CONF_IS_GAS,
    CONF_IS_HOT,
    CONF_IS_LIGHT,
    CONF_IS_LOCKED,
    CONF_IS_MOIST,
    CONF_IS_MOTION,
    CONF_IS_MOVING,
    CONF_IS_OCCUPIED,
    CONF_IS_OPEN,
    CONF_IS_PLUGGED_IN,
    CONF_IS_POWERED,
    CONF_IS_PRESENT,
    CONF_IS_PROBLEM,
    CONF_IS_SMOKE,
    CONF_IS_SOUND,
    CONF_IS_UNSAFE,
    CONF_IS_VIBRATION,
    CONF_IS_ON,
]

IS_OFF = [
    CONF_IS_NOT_BAT_LOW,
    CONF_IS_NOT_COLD,
    CONF_IS_NOT_CONNECTED,
    CONF_IS_NOT_HOT,
    CONF_IS_NOT_LOCKED,
    CONF_IS_NOT_MOIST,
    CONF_IS_NOT_MOVING,
    CONF_IS_NOT_OCCUPIED,
    CONF_IS_NOT_OPEN,
    CONF_IS_NOT_PLUGGED_IN,
    CONF_IS_NOT_POWERED,
    CONF_IS_NOT_PRESENT,
    CONF_IS_NOT_UNSAFE,
    CONF_IS_NO_GAS,
    CONF_IS_NO_LIGHT,
    CONF_IS_NO_MOTION,
    CONF_IS_NO_PROBLEM,
    CONF_IS_NO_SMOKE,
    CONF_IS_NO_SOUND,
    CONF_IS_NO_VIBRATION,
    CONF_IS_OFF,
]

TURNED_ON = [
    CONF_BAT_LOW,
    CONF_COLD,
    CONF_CONNECTED,
    CONF_GAS,
    CONF_HOT,
    CONF_LIGHT,
    CONF_LOCKED,
    CONF_MOIST,
    CONF_MOTION,
    CONF_MOVING,
    CONF_OCCUPIED,
    CONF_OPEN,
    CONF_PLUGGED_IN,
    CONF_POWERED,
    CONF_PRESENT,
    CONF_PROBLEM,
    CONF_SMOKE,
    CONF_SOUND,
    CONF_UNSAFE,
    CONF_VIBRATION,
    CONF_TURNED_ON,
]

TURNED_OFF = [
    CONF_NOT_BAT_LOW,
    CONF_NOT_COLD,
    CONF_NOT_CONNECTED,
    CONF_NOT_HOT,
    CONF_NOT_LOCKED,
    CONF_NOT_MOIST,
    CONF_NOT_MOVING,
    CONF_NOT_OCCUPIED,
    CONF_NOT_OPEN,
    CONF_NOT_PLUGGED_IN,
    CONF_NOT_POWERED,
    CONF_NOT_PRESENT,
    CONF_NOT_UNSAFE,
    CONF_NO_GAS,
    CONF_NO_LIGHT,
    CONF_NO_MOTION,
    CONF_NO_PROBLEM,
    CONF_NO_SMOKE,
    CONF_NO_SOUND,
    CONF_NO_VIBRATION,
    CONF_TURNED_OFF,
]

ENTITY_CONDITIONS = {
    DEVICE_CLASS_BATTERY: [
        {CONF_TYPE: CONF_IS_BAT_LOW},
        {CONF_TYPE: CONF_IS_NOT_BAT_LOW},
    ],
    DEVICE_CLASS_COLD: [{CONF_TYPE: CONF_IS_COLD}, {CONF_TYPE: CONF_IS_NOT_COLD}],
    DEVICE_CLASS_CONNECTIVITY: [
        {CONF_TYPE: CONF_IS_CONNECTED},
        {CONF_TYPE: CONF_IS_NOT_CONNECTED},
    ],
    DEVICE_CLASS_DOOR: [{CONF_TYPE: CONF_IS_OPEN}, {CONF_TYPE: CONF_IS_NOT_OPEN}],
    DEVICE_CLASS_GARAGE_DOOR: [
        {CONF_TYPE: CONF_IS_OPEN},
        {CONF_TYPE: CONF_IS_NOT_OPEN},
    ],
    DEVICE_CLASS_GAS: [{CONF_TYPE: CONF_IS_GAS}, {CONF_TYPE: CONF_IS_NO_GAS}],
    DEVICE_CLASS_HEAT: [{CONF_TYPE: CONF_IS_HOT}, {CONF_TYPE: CONF_IS_NOT_HOT}],
    DEVICE_CLASS_LIGHT: [{CONF_TYPE: CONF_IS_LIGHT}, {CONF_TYPE: CONF_IS_NO_LIGHT}],
    DEVICE_CLASS_LOCK: [{CONF_TYPE: CONF_IS_LOCKED}, {CONF_TYPE: CONF_IS_NOT_LOCKED}],
    DEVICE_CLASS_MOISTURE: [{CONF_TYPE: CONF_IS_MOIST}, {CONF_TYPE: CONF_IS_NOT_MOIST}],
    DEVICE_CLASS_MOTION: [{CONF_TYPE: CONF_IS_MOTION}, {CONF_TYPE: CONF_IS_NO_MOTION}],
    DEVICE_CLASS_MOVING: [{CONF_TYPE: CONF_IS_MOVING}, {CONF_TYPE: CONF_IS_NOT_MOVING}],
    DEVICE_CLASS_OCCUPANCY: [
        {CONF_TYPE: CONF_IS_OCCUPIED},
        {CONF_TYPE: CONF_IS_NOT_OCCUPIED},
    ],
    DEVICE_CLASS_OPENING: [{CONF_TYPE: CONF_IS_OPEN}, {CONF_TYPE: CONF_IS_NOT_OPEN}],
    DEVICE_CLASS_PLUG: [
        {CONF_TYPE: CONF_IS_PLUGGED_IN},
        {CONF_TYPE: CONF_IS_NOT_PLUGGED_IN},
    ],
    DEVICE_CLASS_POWER: [
        {CONF_TYPE: CONF_IS_POWERED},
        {CONF_TYPE: CONF_IS_NOT_POWERED},
    ],
    DEVICE_CLASS_PRESENCE: [
        {CONF_TYPE: CONF_IS_PRESENT},
        {CONF_TYPE: CONF_IS_NOT_PRESENT},
    ],
    DEVICE_CLASS_PROBLEM: [
        {CONF_TYPE: CONF_IS_PROBLEM},
        {CONF_TYPE: CONF_IS_NO_PROBLEM},
    ],
    DEVICE_CLASS_SAFETY: [{CONF_TYPE: CONF_IS_UNSAFE}, {CONF_TYPE: CONF_IS_NOT_UNSAFE}],
    DEVICE_CLASS_SMOKE: [{CONF_TYPE: CONF_IS_SMOKE}, {CONF_TYPE: CONF_IS_NO_SMOKE}],
    DEVICE_CLASS_SOUND: [{CONF_TYPE: CONF_IS_SOUND}, {CONF_TYPE: CONF_IS_NO_SOUND}],
    DEVICE_CLASS_VIBRATION: [
        {CONF_TYPE: CONF_IS_VIBRATION},
        {CONF_TYPE: CONF_IS_NO_VIBRATION},
    ],
    DEVICE_CLASS_WINDOW: [{CONF_TYPE: CONF_IS_OPEN}, {CONF_TYPE: CONF_IS_NOT_OPEN}],
    DEVICE_CLASS_NONE: [{CONF_TYPE: CONF_IS_ON}, {CONF_TYPE: CONF_IS_OFF}],
}

ENTITY_TRIGGERS = {
    DEVICE_CLASS_BATTERY: [{CONF_TYPE: CONF_BAT_LOW}, {CONF_TYPE: CONF_NOT_BAT_LOW}],
    DEVICE_CLASS_COLD: [{CONF_TYPE: CONF_COLD}, {CONF_TYPE: CONF_NOT_COLD}],
    DEVICE_CLASS_CONNECTIVITY: [
        {CONF_TYPE: CONF_CONNECTED},
        {CONF_TYPE: CONF_NOT_CONNECTED},
    ],
    DEVICE_CLASS_DOOR: [{CONF_TYPE: CONF_OPEN}, {CONF_TYPE: CONF_NOT_OPEN}],
    DEVICE_CLASS_GARAGE_DOOR: [{CONF_TYPE: CONF_OPEN}, {CONF_TYPE: CONF_NOT_OPEN}],
    DEVICE_CLASS_GAS: [{CONF_TYPE: CONF_GAS}, {CONF_TYPE: CONF_NO_GAS}],
    DEVICE_CLASS_HEAT: [{CONF_TYPE: CONF_HOT}, {CONF_TYPE: CONF_NOT_HOT}],
    DEVICE_CLASS_LIGHT: [{CONF_TYPE: CONF_LIGHT}, {CONF_TYPE: CONF_NO_LIGHT}],
    DEVICE_CLASS_LOCK: [{CONF_TYPE: CONF_LOCKED}, {CONF_TYPE: CONF_NOT_LOCKED}],
    DEVICE_CLASS_MOISTURE: [{CONF_TYPE: CONF_MOIST}, {CONF_TYPE: CONF_NOT_MOIST}],
    DEVICE_CLASS_MOTION: [{CONF_TYPE: CONF_MOTION}, {CONF_TYPE: CONF_NO_MOTION}],
    DEVICE_CLASS_MOVING: [{CONF_TYPE: CONF_MOVING}, {CONF_TYPE: CONF_NOT_MOVING}],
    DEVICE_CLASS_OCCUPANCY: [
        {CONF_TYPE: CONF_OCCUPIED},
        {CONF_TYPE: CONF_NOT_OCCUPIED},
    ],
    DEVICE_CLASS_OPENING: [{CONF_TYPE: CONF_OPEN}, {CONF_TYPE: CONF_NOT_OPEN}],
    DEVICE_CLASS_PLUG: [{CONF_TYPE: CONF_PLUGGED_IN}, {CONF_TYPE: CONF_NOT_PLUGGED_IN}],
    DEVICE_CLASS_POWER: [{CONF_TYPE: CONF_POWERED}, {CONF_TYPE: CONF_NOT_POWERED}],
    DEVICE_CLASS_PRESENCE: [{CONF_TYPE: CONF_PRESENT}, {CONF_TYPE: CONF_NOT_PRESENT}],
    DEVICE_CLASS_PROBLEM: [{CONF_TYPE: CONF_PROBLEM}, {CONF_TYPE: CONF_NO_PROBLEM}],
    DEVICE_CLASS_SAFETY: [{CONF_TYPE: CONF_UNSAFE}, {CONF_TYPE: CONF_NOT_UNSAFE}],
    DEVICE_CLASS_SMOKE: [{CONF_TYPE: CONF_SMOKE}, {CONF_TYPE: CONF_NO_SMOKE}],
    DEVICE_CLASS_SOUND: [{CONF_TYPE: CONF_SOUND}, {CONF_TYPE: CONF_NO_SOUND}],
    DEVICE_CLASS_VIBRATION: [
        {CONF_TYPE: CONF_VIBRATION},
        {CONF_TYPE: CONF_NO_VIBRATION},
    ],
    DEVICE_CLASS_WINDOW: [{CONF_TYPE: CONF_OPEN}, {CONF_TYPE: CONF_NOT_OPEN}],
    DEVICE_CLASS_NONE: [{CONF_TYPE: CONF_TURNED_ON}, {CONF_TYPE: CONF_TURNED_OFF}],
}

CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONDITION): "device",
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(IS_OFF + IS_ON),
    }
)

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "device",
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TURNED_OFF + TURNED_ON),
    }
)


def async_condition_from_config(config, config_validation):
    """Evaluate state based on configuration."""
    config = CONDITION_SCHEMA(config)
    condition_type = config[CONF_TYPE]
    if condition_type in IS_ON:
        stat = "on"
    else:
        stat = "off"
    state_config = {
        condition.CONF_CONDITION: "state",
        condition.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        condition.CONF_STATE: stat,
    }

    return condition.state_from_config(state_config, config_validation)


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)
    trigger_type = config[CONF_TYPE]
    if trigger_type in TURNED_ON:
        from_state = "off"
        to_state = "on"
    else:
        from_state = "on"
        to_state = "off"
    state_config = {
        state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_FROM: from_state,
        state.CONF_TO: to_state,
    }

    return await state.async_trigger(hass, state_config, action, automation_info)


def _is_domain(entity, domain):
    return split_entity_id(entity.entity_id)[0] == domain


async def _async_get_automations(hass, device_id, automation_templates, domain):
    """List device automations."""
    automations = []
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entities = async_entries_for_device(entity_registry, device_id)
    domain_entities = [x for x in entities if _is_domain(x, domain)]
    for entity in domain_entities:
        device_class = DEVICE_CLASS_NONE
        entity_id = entity.entity_id
        entity = hass.states.get(entity_id)
        if entity and ATTR_DEVICE_CLASS in entity.attributes:
            device_class = entity.attributes[ATTR_DEVICE_CLASS]
        automation_template = automation_templates[device_class]

        for automation in automation_template:
            automation = dict(automation)
            automation.update(device_id=device_id, entity_id=entity_id, domain=domain)
            automations.append(automation)

    return automations


async def async_get_conditions(hass, device_id):
    """List device conditions."""
    automations = await _async_get_automations(
        hass, device_id, ENTITY_CONDITIONS, DOMAIN
    )
    for automation in automations:
        automation.update(condition="device")
    return automations


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    automations = await _async_get_automations(hass, device_id, ENTITY_TRIGGERS, DOMAIN)
    for automation in automations:
        automation.update(platform="device")
    return automations
