"""Device triggers for the Bang & Olufsen integration."""

from __future__ import annotations

from typing import Any, cast

from mozart_api.models import PairedRemote
from mozart_api.mozart_client import MozartClient
import voluptuous as vol

from homeassistant.components.automation import TriggerActionType, TriggerInfo
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    BANG_OLUFSEN_EVENT,
    BEO_REMOTE_CONTROL_KEYS,
    BEO_REMOTE_KEY_EVENTS,
    BEO_REMOTE_KEYS,
    BEO_REMOTE_LIGHT_KEYS,
    BEO_REMOTE_SUBMENU_CONTROL,
    BEO_REMOTE_SUBMENU_LIGHT,
    BEO_REMOTE_SUBMENUS,
    CONF_SUBTYPE,
    DEVICE_BUTTON_EVENTS,
    DEVICE_BUTTONS,
    DEVICE_TRIGGER_TYPES,
    DOMAIN,
)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(DEVICE_TRIGGER_TYPES),
        vol.Required(CONF_TYPE): vol.In(BEO_REMOTE_KEY_EVENTS + DEVICE_BUTTON_EVENTS),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Bang & Olufsen devices."""
    # Check if a Beoremote One is connected to the device and remote triggers should be added

    # Get the serial number
    device_registry = dr.async_get(hass)
    serial_number = list(device_registry.devices[device_id].identifiers)[0][1]

    # Get the entity id
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        Platform.MEDIA_PLAYER, DOMAIN, serial_number
    )
    assert entity_id

    entry = entity_registry.async_get(entity_id)
    assert entry

    client: MozartClient = hass.data[DOMAIN][entry.config_entry_id].client

    # Get if a remote control is connected
    bluetooth_remote_list = await client.get_bluetooth_remotes()
    remote_control_available = bool(
        len(cast(list[PairedRemote], bluetooth_remote_list.items))
    )

    # Always add default triggers
    triggers: list[dict[str, Any]] = [
        {
            CONF_PLATFORM: CONF_DEVICE,
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
            CONF_SUBTYPE: device_button,
        }
        for device_button in DEVICE_BUTTONS
        for trigger_type in DEVICE_BUTTON_EVENTS
    ]
    # Add remote triggers if available
    if remote_control_available:
        # Add common triggers
        triggers.extend(
            [
                {
                    CONF_PLATFORM: CONF_DEVICE,
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: trigger_type,
                    CONF_SUBTYPE: remote_button,
                }
                for remote_button in [
                    f"{submenu}/{key}"
                    for submenu in BEO_REMOTE_SUBMENUS
                    for key in BEO_REMOTE_KEYS
                ]
                for trigger_type in BEO_REMOTE_KEY_EVENTS
            ]
        )
        # Add Control triggers
        triggers.extend(
            [
                {
                    CONF_PLATFORM: CONF_DEVICE,
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: trigger_type,
                    CONF_SUBTYPE: remote_button,
                }
                for remote_button in [
                    f"{BEO_REMOTE_SUBMENU_CONTROL}/{key}"
                    for key in BEO_REMOTE_CONTROL_KEYS
                ]
                for trigger_type in BEO_REMOTE_KEY_EVENTS
            ]
        )

        # Add Light triggers
        triggers.extend(
            [
                {
                    CONF_PLATFORM: CONF_DEVICE,
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: trigger_type,
                    CONF_SUBTYPE: remote_button,
                }
                for remote_button in [
                    f"{BEO_REMOTE_SUBMENU_LIGHT}/{key}" for key in BEO_REMOTE_LIGHT_KEYS
                ]
                for trigger_type in BEO_REMOTE_KEY_EVENTS
            ]
        )
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: BANG_OLUFSEN_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
                CONF_SUBTYPE: config[CONF_SUBTYPE],
            },
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type=CONF_DEVICE
    )
