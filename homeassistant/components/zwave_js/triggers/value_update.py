"""Offer Z-Wave JS value update listening automation rules."""
from __future__ import annotations

import logging
from typing import Any, Callable

import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.event import Event
from zwave_js_server.model.value import Value, get_value_id

from homeassistant.components.zwave_js.const import (
    ATTR_COMMAND_CLASS,
    ATTR_CURRENT_VALUE,
    ATTR_ENDPOINT,
    ATTR_NODE_ID,
    ATTR_PREVIOUS_VALUE,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
)
from homeassistant.components.zwave_js.helpers import (
    async_get_node_from_device_id,
    async_get_node_from_entity_id,
    get_device_id,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_PLATFORM, MATCH_ALL
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORM_TYPE = "zwave_js.value_update"
ATTR_FROM = "from"
ATTR_TO = "to"

VALUE_SCHEMA = vol.Any(
    bool,
    vol.Coerce(int),
    vol.Coerce(float),
    cv.boolean,
    cv.string,
)

TRIGGER_SCHEMA = vol.All(
    cv.TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_PLATFORM): "zwave_js.value_update",
            vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Required(ATTR_COMMAND_CLASS): vol.In(
                {cc.value: cc.name for cc in CommandClass}
            ),
            vol.Required(ATTR_PROPERTY): vol.Any(vol.Coerce(int), cv.string),
            vol.Optional(ATTR_ENDPOINT): vol.Coerce(int),
            vol.Optional(ATTR_PROPERTY_KEY): vol.Any(vol.Coerce(int), cv.string),
            vol.Optional(ATTR_FROM): vol.Any(VALUE_SCHEMA, [VALUE_SCHEMA]),
            vol.Optional(ATTR_TO): vol.Any(VALUE_SCHEMA, [VALUE_SCHEMA]),
        },
    ),
    cv.has_at_least_one_key(ATTR_ENTITY_ID, ATTR_DEVICE_ID),
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: Callable,
    automation_info: dict[str, Any],
    *,
    platform_type: str = PLATFORM_TYPE,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    nodes = set()
    if ATTR_DEVICE_ID in config:
        nodes.update(
            {
                async_get_node_from_device_id(hass, device_id)
                for device_id in config.get(ATTR_DEVICE_ID, [])
            }
        )
    if ATTR_ENTITY_ID in config:
        nodes.update(
            {
                async_get_node_from_entity_id(hass, entity_id)
                for entity_id in config.get(ATTR_ENTITY_ID, [])
            }
        )

    from_value = config.get(ATTR_FROM, MATCH_ALL)
    to_value = config.get(ATTR_TO, MATCH_ALL)
    command_class = config[ATTR_COMMAND_CLASS]
    property_ = config[ATTR_PROPERTY]
    endpoint = config.get(ATTR_ENDPOINT)
    property_key = config.get(ATTR_PROPERTY_KEY)
    unsubs = []
    job = HassJob(action)

    trigger_data: dict = {}
    if automation_info:
        trigger_data = automation_info.get("trigger_data", {})

    @callback
    def async_on_value_updated(
        value: Value, device: dr.DeviceEntry, event: Event
    ) -> None:
        """Handle value update."""
        event_value: Value = event["value"]
        prev_value = event["args"]["prevValue"]
        curr_value = event["args"]["newValue"]
        if event_value != value:
            return
        for value_to_eval, match in ((prev_value, from_value), (curr_value, to_value)):
            if (
                match != MATCH_ALL
                and value_to_eval != match
                and not (isinstance(match, list) and value_to_eval in match)
            ):
                return

        device_name = device.name_by_user or device.name

        payload = {
            **trigger_data,
            CONF_PLATFORM: platform_type,
            ATTR_DEVICE_ID: device.id,
            ATTR_NODE_ID: value.node.node_id,
            ATTR_PREVIOUS_VALUE: prev_value,
            ATTR_CURRENT_VALUE: curr_value,
            "description": f"Z-Wave value {value_id} updated on {device_name}",
        }
        if ATTR_ENTITY_ID in config:
            payload[ATTR_ENTITY_ID] = config[ATTR_ENTITY_ID]

        hass.async_run_hass_job(job, {"trigger": payload})

    for node in nodes:
        device_identifier = get_device_id(node.client, node)
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get_device({device_identifier})
        assert device
        value_id = get_value_id(node, command_class, property_, endpoint, property_key)
        value = node.values[value_id]
        unsubs.append(
            node.on(
                "value updated",
                lambda event: async_on_value_updated(value, device, event),
            )
        )

    @callback
    def async_remove() -> None:
        """Remove state listeners async."""
        for unsub in unsubs:
            unsub()
        unsubs.clear()

    return async_remove
