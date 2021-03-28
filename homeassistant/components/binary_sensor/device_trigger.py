"""Provides device triggers for binary sensors."""
import voluptuous as vol

from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.const import (
    CONF_TURNED_OFF,
    CONF_TURNED_ON,
)
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID, CONF_FOR, CONF_TYPE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_registry import async_entries_for_device

from . import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_BATTERY_CHARGING,
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
    DOMAIN,
)

# mypy: allow-untyped-defs, no-check-untyped-defs

DEVICE_CLASS_NONE = "none"

CONF_BAT_LOW = "bat_low"
CONF_NOT_BAT_LOW = "not_bat_low"
CONF_CHARGING = "charging"
CONF_NOT_CHARGING = "not_charging"
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
CONF_OPENED = "opened"
CONF_NOT_OPENED = "not_opened"


TURNED_ON = [
    CONF_BAT_LOW,
    CONF_COLD,
    CONF_CONNECTED,
    CONF_GAS,
    CONF_HOT,
    CONF_LIGHT,
    CONF_NOT_LOCKED,
    CONF_MOIST,
    CONF_MOTION,
    CONF_MOVING,
    CONF_OCCUPIED,
    CONF_OPENED,
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
    CONF_LOCKED,
    CONF_NOT_MOIST,
    CONF_NOT_MOVING,
    CONF_NOT_OCCUPIED,
    CONF_NOT_OPENED,
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


ENTITY_TRIGGERS = {
    DEVICE_CLASS_BATTERY: [{CONF_TYPE: CONF_BAT_LOW}, {CONF_TYPE: CONF_NOT_BAT_LOW}],
    DEVICE_CLASS_BATTERY_CHARGING: [
        {CONF_TYPE: CONF_CHARGING},
        {CONF_TYPE: CONF_NOT_CHARGING},
    ],
    DEVICE_CLASS_COLD: [{CONF_TYPE: CONF_COLD}, {CONF_TYPE: CONF_NOT_COLD}],
    DEVICE_CLASS_CONNECTIVITY: [
        {CONF_TYPE: CONF_CONNECTED},
        {CONF_TYPE: CONF_NOT_CONNECTED},
    ],
    DEVICE_CLASS_DOOR: [{CONF_TYPE: CONF_OPENED}, {CONF_TYPE: CONF_NOT_OPENED}],
    DEVICE_CLASS_GARAGE_DOOR: [{CONF_TYPE: CONF_OPENED}, {CONF_TYPE: CONF_NOT_OPENED}],
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
    DEVICE_CLASS_OPENING: [{CONF_TYPE: CONF_OPENED}, {CONF_TYPE: CONF_NOT_OPENED}],
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
    DEVICE_CLASS_WINDOW: [{CONF_TYPE: CONF_OPENED}, {CONF_TYPE: CONF_NOT_OPENED}],
    DEVICE_CLASS_NONE: [{CONF_TYPE: CONF_TURNED_ON}, {CONF_TYPE: CONF_TURNED_OFF}],
}


TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TURNED_OFF + TURNED_ON),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    trigger_type = config[CONF_TYPE]
    if trigger_type in TURNED_ON:
        to_state = "on"
    else:
        to_state = "off"

    state_config = {
        state_trigger.CONF_PLATFORM: "state",
        state_trigger.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state_trigger.CONF_TO: to_state,
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]

    state_config = state_trigger.TRIGGER_SCHEMA(state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    triggers = []
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entries = [
        entry
        for entry in async_entries_for_device(entity_registry, device_id)
        if entry.domain == DOMAIN
    ]

    for entry in entries:
        device_class = DEVICE_CLASS_NONE
        state = hass.states.get(entry.entity_id)
        if state:
            device_class = state.attributes.get(ATTR_DEVICE_CLASS)

        templates = ENTITY_TRIGGERS.get(
            device_class, ENTITY_TRIGGERS[DEVICE_CLASS_NONE]
        )

        triggers.extend(
            {
                **automation,
                "platform": "device",
                "device_id": device_id,
                "entity_id": entry.entity_id,
                "domain": DOMAIN,
            }
            for automation in templates
        )

    return triggers


async def async_get_trigger_capabilities(hass, config):
    """List trigger capabilities."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }
