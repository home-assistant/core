"""Implement device conditions for binary sensor."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation.const import CONF_IS_OFF, CONF_IS_ON
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID, CONF_FOR, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.entity_registry import (
    async_entries_for_device,
    async_get_registry,
)
from homeassistant.helpers.typing import ConfigType

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

DEVICE_CLASS_NONE = "none"

CONF_IS_BAT_LOW = "is_bat_low"
CONF_IS_NOT_BAT_LOW = "is_not_bat_low"
CONF_IS_CHARGING = "is_charging"
CONF_IS_NOT_CHARGING = "is_not_charging"
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

IS_ON = [
    CONF_IS_BAT_LOW,
    CONF_IS_CHARGING,
    CONF_IS_COLD,
    CONF_IS_CONNECTED,
    CONF_IS_GAS,
    CONF_IS_HOT,
    CONF_IS_LIGHT,
    CONF_IS_NOT_LOCKED,
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
    CONF_IS_NOT_CHARGING,
    CONF_IS_NOT_COLD,
    CONF_IS_NOT_CONNECTED,
    CONF_IS_NOT_HOT,
    CONF_IS_LOCKED,
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

ENTITY_CONDITIONS = {
    DEVICE_CLASS_BATTERY: [
        {CONF_TYPE: CONF_IS_BAT_LOW},
        {CONF_TYPE: CONF_IS_NOT_BAT_LOW},
    ],
    DEVICE_CLASS_BATTERY_CHARGING: [
        {CONF_TYPE: CONF_IS_CHARGING},
        {CONF_TYPE: CONF_IS_NOT_CHARGING},
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

CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(IS_OFF + IS_ON),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions."""
    conditions: list[dict[str, str]] = []
    entity_registry = await async_get_registry(hass)
    entries = [
        entry
        for entry in async_entries_for_device(entity_registry, device_id)
        if entry.domain == DOMAIN
    ]

    for entry in entries:
        device_class = DEVICE_CLASS_NONE
        state = hass.states.get(entry.entity_id)
        if state and ATTR_DEVICE_CLASS in state.attributes:
            device_class = state.attributes[ATTR_DEVICE_CLASS]

        templates = ENTITY_CONDITIONS.get(
            device_class, ENTITY_CONDITIONS[DEVICE_CLASS_NONE]
        )

        conditions.extend(
            {
                **template,
                "condition": "device",
                "device_id": device_id,
                "entity_id": entry.entity_id,
                "domain": DOMAIN,
            }
            for template in templates
        )

    return conditions


@callback
def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Evaluate state based on configuration."""
    if config_validation:
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
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]

    return condition.state_from_config(state_config)


async def async_get_condition_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List condition capabilities."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }
