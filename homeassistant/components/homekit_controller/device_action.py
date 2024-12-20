"""Provides device actions for HomeKit devices."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from aiohomekit.model import Characteristic
from aiohomekit.model.characteristics import CharacteristicsTypes
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
import homeassistant.util.dt as dt_util

from .const import ACTIONS, DOMAIN, KNOWN_DEVICES

if TYPE_CHECKING:
    from .connection import HKDevice

CONF_HOLD_DURATION = "hold_duration"
CONF_ECOBEE_TIMEZONE = "ecobee_timezone"
ECOBEE_SET_HOLD_DURATION = "ecobee_set_hold_duration"
SET_HOLD_DURATION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): ECOBEE_SET_HOLD_DURATION,
        vol.Required(CONF_HOLD_DURATION): cv.time_period,
        vol.Required(CONF_ECOBEE_TIMEZONE): cv.time_zone,
    }
)

ACTIONS_BY_CHARACTERISTIC: dict[str, str] = {
    CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME: ECOBEE_SET_HOLD_DURATION
}

ACTION_SCHEMA = vol.Any(SET_HOLD_DURATION_SCHEMA)


class ActionDevice:
    """Tracks the actions for a specific device id."""

    def __init__(self, hkid: str) -> None:
        """Initialize tracking a device for actions."""
        self.hkid = hkid
        self.actions: dict[str, tuple[int, int]] = {}

    def add_action(self, aid: int, iid: int, action_type: str) -> None:
        """Add an action that's available for a particular accessory/service."""
        self.actions[action_type] = (aid, iid)


async def async_setup_actions_for_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Actions aren't entities so have no state, but need to keep track of the available actions for a device id."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_characteristic(char: Characteristic) -> bool:
        if not (action_type := ACTIONS_BY_CHARACTERISTIC.get(char.type)):
            return False

        device_id = conn.devices[char.service.accessory.aid]

        action_device: ActionDevice = async_get_or_create_action_device(
            hass, device_id, hkid
        )

        if action_type in action_device.actions:
            # Action is already registered
            return False

        action_device.add_action(
            char.service.accessory.aid, char.service.iid, action_type
        )
        return False

    conn.add_char_factory(async_add_characteristic)


@callback
def async_get_or_create_action_device(
    hass: HomeAssistant, device_id: str, hkid: str
) -> ActionDevice:
    """Get or create an action device reference for a given device id."""

    action_devices: dict[str, ActionDevice] = hass.data.setdefault(ACTIONS, {})
    if not (actionDevice := action_devices.get(device_id)):
        actionDevice = ActionDevice(hkid)
        action_devices[device_id] = actionDevice

    return actionDevice


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions."""

    if device_id not in hass.data.get(ACTIONS, {}):
        return []

    actionDevice: ActionDevice = hass.data[ACTIONS][device_id]

    actions = []

    global_type = {
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    for action_type in actionDevice.actions:
        actions.append({**global_type, CONF_TYPE: action_type})
        break

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    action_type = config[CONF_TYPE]
    device_id = config[CONF_DEVICE_ID]

    actionDevice: ActionDevice = hass.data[ACTIONS][device_id]
    conn: HKDevice = hass.data[KNOWN_DEVICES][actionDevice.hkid]

    aid, iid = actionDevice.actions[action_type]

    if action_type == ECOBEE_SET_HOLD_DURATION:
        # New hold end time will need to be a time local to the ecobee device, so use the specified time zone
        delta: timedelta = config[CONF_HOLD_DURATION]
        timezone = await dt_util.async_get_time_zone(config[CONF_ECOBEE_TIMEZONE])
        now = datetime.now(timezone)
        holdEnd = now + delta
        holdEndString = holdEnd.strftime("%Y-%m-%dT%H:%M:%S")

        service = conn.entity_map.aid(aid).services.iid(iid)

        if service.has(CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME):
            payload = service.build_update(
                {
                    CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME: holdEndString,
                }
            )
            await conn.put_characteristics(payload)


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    action_type = config[CONF_TYPE]

    fields = {}

    if action_type == ECOBEE_SET_HOLD_DURATION:
        fields[vol.Required(CONF_HOLD_DURATION)] = cv.string
        fields[vol.Required(CONF_ECOBEE_TIMEZONE)] = cv.string

    return {"extra_fields": vol.Schema(fields)}
