"""Provides device automations for homekit devices."""
from __future__ import annotations

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.characteristics.const import InputEventValues
from aiohomekit.model.services import ServicesTypes
from aiohomekit.utils import clamp_enum_to_char
import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, KNOWN_DEVICES, TRIGGERS

TRIGGER_TYPES = {
    "doorbell",
    "button1",
    "button2",
    "button3",
    "button4",
    "button5",
    "button6",
    "button7",
    "button8",
    "button9",
    "button10",
}
TRIGGER_SUBTYPES = {"single_press", "double_press", "long_press"}

CONF_IID = "iid"
CONF_SUBTYPE = "subtype"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_SUBTYPE): vol.In(TRIGGER_SUBTYPES),
    }
)

HK_TO_HA_INPUT_EVENT_VALUES = {
    InputEventValues.SINGLE_PRESS: "single_press",
    InputEventValues.DOUBLE_PRESS: "double_press",
    InputEventValues.LONG_PRESS: "long_press",
}


class TriggerSource:
    """Represents a stateless source of event data from HomeKit."""

    def __init__(self, connection, aid, triggers):
        """Initialize a set of triggers for a device."""
        self._hass = connection.hass
        self._connection = connection
        self._aid = aid
        self._triggers = {}
        for trigger in triggers:
            self._triggers[(trigger["type"], trigger["subtype"])] = trigger
        self._callbacks = {}

    def fire(self, iid, value):
        """Process events that have been received from a HomeKit accessory."""
        for event_handler in self._callbacks.get(iid, []):
            event_handler(value)

    def async_get_triggers(self):
        """List device triggers for homekit devices."""
        yield from self._triggers

    async def async_attach_trigger(
        self,
        config: TRIGGER_SCHEMA,
        action: AutomationActionType,
        automation_info: dict,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""
        trigger_data = (
            automation_info.get("trigger_data", {}) if automation_info else {}
        )

        def event_handler(char):
            if config[CONF_SUBTYPE] != HK_TO_HA_INPUT_EVENT_VALUES[char["value"]]:
                return
            self._hass.async_create_task(
                action({"trigger": {**trigger_data, **config}})
            )

        trigger = self._triggers[config[CONF_TYPE], config[CONF_SUBTYPE]]
        iid = trigger["characteristic"]

        self._connection.add_watchable_characteristics([(self._aid, iid)])
        self._callbacks.setdefault(iid, []).append(event_handler)

        def async_remove_handler():
            if iid in self._callbacks:
                self._callbacks[iid].remove(event_handler)

        return async_remove_handler


def enumerate_stateless_switch(service):
    """Enumerate a stateless switch, like a single button."""

    # A stateless switch that has a SERVICE_LABEL_INDEX is part of a group
    # And is handled separately
    if (
        service.has(CharacteristicsTypes.SERVICE_LABEL_INDEX)
        and len(service.linked) > 0
    ):
        return []

    char = service[CharacteristicsTypes.INPUT_EVENT]

    # HomeKit itself supports single, double and long presses. But the
    # manufacturer might not - clamp options to what they say.
    all_values = clamp_enum_to_char(InputEventValues, char)

    return [
        {
            "characteristic": char.iid,
            "value": event_type,
            "type": "button1",
            "subtype": HK_TO_HA_INPUT_EVENT_VALUES[event_type],
        }
        for event_type in all_values
    ]


def enumerate_stateless_switch_group(service):
    """Enumerate a group of stateless switches, like a remote control."""
    switches = list(
        service.accessory.services.filter(
            service_type=ServicesTypes.STATELESS_PROGRAMMABLE_SWITCH,
            child_service=service,
            order_by=[CharacteristicsTypes.SERVICE_LABEL_INDEX],
        )
    )

    results = []
    for idx, switch in enumerate(switches):
        char = switch[CharacteristicsTypes.INPUT_EVENT]

        # HomeKit itself supports single, double and long presses. But the
        # manufacturer might not - clamp options to what they say.
        all_values = clamp_enum_to_char(InputEventValues, char)

        for event_type in all_values:
            results.append(
                {
                    "characteristic": char.iid,
                    "value": event_type,
                    "type": f"button{idx + 1}",
                    "subtype": HK_TO_HA_INPUT_EVENT_VALUES[event_type],
                }
            )
    return results


def enumerate_doorbell(service):
    """Enumerate doorbell buttons."""
    input_event = service[CharacteristicsTypes.INPUT_EVENT]

    # HomeKit itself supports single, double and long presses. But the
    # manufacturer might not - clamp options to what they say.
    all_values = clamp_enum_to_char(InputEventValues, input_event)

    results = []
    for event_type in all_values:
        results.append(
            {
                "characteristic": input_event.iid,
                "value": event_type,
                "type": "doorbell",
                "subtype": HK_TO_HA_INPUT_EVENT_VALUES[event_type],
            }
        )
    return results


TRIGGER_FINDERS = {
    ServicesTypes.SERVICE_LABEL: enumerate_stateless_switch_group,
    ServicesTypes.STATELESS_PROGRAMMABLE_SWITCH: enumerate_stateless_switch,
    ServicesTypes.DOORBELL: enumerate_doorbell,
}


async def async_setup_triggers_for_entry(hass: HomeAssistant, config_entry):
    """Triggers aren't entities as they have no state, but we still need to set them up for a config entry."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service):
        aid = service.accessory.aid
        service_type = service.short_type

        # If not a known service type then we can't handle any stateless events for it
        if service_type not in TRIGGER_FINDERS:
            return False

        # We can't have multiple trigger sources for the same device id
        # Can't have a doorbell and a remote control in the same accessory
        # They have to be different accessories (they can be on the same bridge)
        # In practice, this is inline with what iOS actually supports AFAWCT.
        device_id = conn.devices[aid]
        if device_id in hass.data[TRIGGERS]:
            return False

        # Just because we recognise the service type doesn't mean we can actually
        # extract any triggers - so only proceed if we can
        triggers = TRIGGER_FINDERS[service_type](service)
        if len(triggers) == 0:
            return False

        trigger = TriggerSource(conn, aid, triggers)
        hass.data[TRIGGERS][device_id] = trigger

        return True

    conn.add_listener(async_add_service)


def async_fire_triggers(conn, events):
    """Process events generated by a HomeKit accessory into automation triggers."""
    for (aid, iid), ev in events.items():
        if aid in conn.devices:
            device_id = conn.devices[aid]
            if device_id in conn.hass.data[TRIGGERS]:
                source = conn.hass.data[TRIGGERS][device_id]
                source.fire(iid, ev)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for homekit devices."""

    if device_id not in hass.data.get(TRIGGERS, {}):
        return []

    device = hass.data[TRIGGERS][device_id]

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger,
            CONF_SUBTYPE: subtype,
        }
        for trigger, subtype in device.async_get_triggers()
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    device_id = config[CONF_DEVICE_ID]
    device = hass.data[TRIGGERS][device_id]
    return await device.async_attach_trigger(config, action, automation_info)
