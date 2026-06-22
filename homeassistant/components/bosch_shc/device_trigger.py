"""Provides device triggers for Bosch Smart Home Controller integration."""

from boschshcpy import SHCDevice, SHCSession
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    ALARM_EVENTS_SUBTYPES_SD,
    ALARM_EVENTS_SUBTYPES_SDS,
    ATTR_EVENT_SUBTYPE,
    ATTR_EVENT_TYPE,
    CONF_SUBTYPE,
    DATA_SESSION,
    DOMAIN,
    EVENT_BOSCH_SHC,
    INPUTS_EVENTS_SUBTYPES_SWITCH2,
    INPUTS_EVENTS_SUBTYPES_WRC2,
    LOGGER,
    SUPPORTED_INPUTS_EVENTS_TYPES,
)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(SUPPORTED_INPUTS_EVENTS_TYPES),
        vol.Required(CONF_SUBTYPE): str,
    }
)


async def get_device_from_id(hass, device_id) -> tuple[SHCDevice, str]:
    """Get the device for the given device id."""
    dev_registry = dr.async_get(hass)
    for config_entry in hass.data[DOMAIN]:
        session: SHCSession = hass.data[DOMAIN][config_entry][DATA_SESSION]

        for shc_device in session.devices:
            device = dev_registry.async_get_device(
                identifiers={(DOMAIN, shc_device.id)}, connections=set()
            )
            if device is None or device.id != device_id:
                continue
            return shc_device, shc_device.device_model

        ids = session.intrusion_system
        if ids:
            device = dev_registry.async_get_device(
                identifiers={(DOMAIN, ids.id)}, connections=set()
            )
            if device is not None and device.id == device_id:
                return ids, "IDS"

        device = dev_registry.async_get_device(
            identifiers={(DOMAIN, session.information.unique_id)}, connections=set()
        )
        if device is not None and device.id == device_id:
            return session, "SHC"

    return None, ""


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for SHC devices."""
    triggers = []

    device, dev_type = await get_device_from_id(hass, device_id)
    if not device:
        raise InvalidDeviceAutomationConfig(f"Device not found: {device_id}")

    if dev_type in {"WRC2", "SWITCH2"}:
        input_triggers: list[tuple[str, str]] = []
        for trigger in SUPPORTED_INPUTS_EVENTS_TYPES:
            if trigger in ("PRESS_SHORT", "PRESS_LONG", "PRESS_LONG_RELEASED"):
                match dev_type:
                    case "WRC2":
                        input_triggers.extend(
                            (trigger, subtype)
                            for subtype in INPUTS_EVENTS_SUBTYPES_WRC2
                        )
                    case "SWITCH2":
                        input_triggers.extend(
                            (trigger, subtype)
                            for subtype in INPUTS_EVENTS_SUBTYPES_SWITCH2
                        )
                    case _:  # pragma: no cover — unreachable: outer guard checks WRC2/SWITCH2
                        LOGGER.debug(
                            "Device type %s unknown, no triggers added.", dev_type
                        )

        for trigger, subtype in input_triggers:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: trigger,
                    CONF_SUBTYPE: subtype,
                }
            )

    if dev_type == "MD":
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: "MOTION",
                CONF_SUBTYPE: "",
            }
        )

    if dev_type == "SD":
        triggers.extend(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: "ALARM",
                CONF_SUBTYPE: subtype,
            }
            for subtype in ALARM_EVENTS_SUBTYPES_SD
        )

    if dev_type == "SMOKE_DETECTION_SYSTEM":
        triggers.extend(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: "ALARM",
                CONF_SUBTYPE: subtype,
            }
            for subtype in ALARM_EVENTS_SUBTYPES_SDS
        )

    if dev_type == "SHC":
        triggers.extend(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: "SCENARIO",
                CONF_SUBTYPE: subtype,
            }
            for subtype in device.scenario_names
        )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    automation_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = None

    config = TRIGGER_SCHEMA(config)
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: EVENT_BOSCH_SHC,
            event_trigger.CONF_EVENT_DATA: {
                ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                ATTR_EVENT_TYPE: config[CONF_TYPE],
                ATTR_EVENT_SUBTYPE: config[CONF_SUBTYPE],
            },
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
