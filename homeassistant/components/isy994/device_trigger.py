"""Provides device triggers for ISY994 Insteon devices.

Triggers are exposed for any entity whose underlying ISY node has a
``node_def_id`` in :data:`SUPPORTED_NODE_DEF_IDS`. This covers SwitchLinc
dimmers and relays, KeypadLinc loads (dimmer or relay), and the secondary
``KeypadButton_ADV`` child nodes that share the same on/off/fast/fade
command set.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final, cast

from pyisy.constants import (
    CMD_FADE_DOWN,
    CMD_FADE_STOP,
    CMD_FADE_UP,
    CMD_OFF,
    CMD_OFF_FAST,
    CMD_ON,
    CMD_ON_FAST,
)
import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_ISY994_CONTROL
from .models import IsyData

CONF_SUBTYPE: Final = "subtype"

TRIGGER_TYPES: Final[dict[str, str]] = {
    "on": CMD_ON,
    "off": CMD_OFF,
    "fast_on": CMD_ON_FAST,
    "fast_off": CMD_OFF_FAST,
    "fade_up": CMD_FADE_UP,
    "fade_down": CMD_FADE_DOWN,
    "fade_stop": CMD_FADE_STOP,
}

SUPPORTED_NODE_DEF_IDS: Final = frozenset(
    {
        "BallastRelayLampSwitch_ADV",
        "DimmerLampSwitch_ADV",
        "DimmerSwitchOnly_ADV",
        "KeypadButton_ADV",
        "KeypadDimmer_ADV",
        "KeypadRelay_ADV",
        "RelayLampOnly_ADV",
        "RelayLampSwitch_ADV",
        "RelaySwitchOnlyPlusQuery_ADV",
    }
)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_SUBTYPE): str,
        vol.Optional(CONF_ENTITY_ID): str,
    }
)


def _resolve_isy_data(hass: HomeAssistant, device_id: str) -> IsyData | None:
    """Return the IsyData backing the given Home Assistant device, if any."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is not None
            and entry.domain == DOMAIN
            and entry.state is ConfigEntryState.LOADED
        ):
            return cast(IsyData, entry.runtime_data)
    return None


def _supported_button_entries(
    hass: HomeAssistant, device_id: str, isy_data: IsyData
) -> Iterator[tuple[er.RegistryEntry, str]]:
    """Yield (entity, node_address) for each entity backed by a supported node."""
    prefix = f"{isy_data.uuid}_"
    for entry in er.async_entries_for_device(
        er.async_get(hass), device_id, include_disabled_entities=False
    ):
        if entry.platform != DOMAIN or not entry.unique_id.startswith(prefix):
            continue
        address = entry.unique_id[len(prefix) :]
        node = isy_data.root.nodes.get_by_id(address)
        if node is None:
            continue
        if getattr(node, "node_def_id", None) in SUPPORTED_NODE_DEF_IDS:
            yield entry, address


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for supported ISY Insteon load/button nodes."""
    isy_data = _resolve_isy_data(hass, device_id)
    if isy_data is None:
        return []

    triggers: list[dict[str, str]] = []
    for entry, address in _supported_button_entries(hass, device_id, isy_data):
        triggers.extend(
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: trigger_type,
                CONF_SUBTYPE: address,
            }
            for trigger_type in TRIGGER_TYPES
        )
    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """No additional fields — type and subtype fully describe the trigger."""
    return {}


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger that filters isy994_control events."""
    device_id: str = config[CONF_DEVICE_ID]
    isy_data = _resolve_isy_data(hass, device_id)
    if isy_data is None:
        raise InvalidDeviceAutomationConfig(
            f"ISY device {device_id} not found or not loaded"
        )

    address = config[CONF_SUBTYPE]
    node = isy_data.root.nodes.get_by_id(address)
    if node is None or getattr(node, "node_def_id", None) not in SUPPORTED_NODE_DEF_IDS:
        raise InvalidDeviceAutomationConfig(
            f"ISY node {address} is not a supported device-trigger source"
        )

    target_unique_id = f"{isy_data.uuid}_{address}"
    target_entity_id: str | None = None
    for entry in er.async_entries_for_device(er.async_get(hass), device_id):
        if entry.platform == DOMAIN and entry.unique_id == target_unique_id:
            target_entity_id = entry.entity_id
            break
    if target_entity_id is None:
        raise InvalidDeviceAutomationConfig(
            f"No ISY entity found for device {device_id} subtype {address}"
        )

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_ISY994_CONTROL,
            event_trigger.CONF_EVENT_DATA: {
                CONF_ENTITY_ID: target_entity_id,
                "control": TRIGGER_TYPES[config[CONF_TYPE]],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
