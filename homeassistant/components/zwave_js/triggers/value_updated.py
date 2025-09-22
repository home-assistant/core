"""Offer Z-Wave JS value updated listening automation trigger."""

from __future__ import annotations

from collections.abc import Callable
import functools
from typing import Any

import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.value import Value, get_value_id_str

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    MATCH_ALL,
)
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionType,
    TriggerConfig,
    TriggerInfo,
    move_top_level_schema_fields_to_options,
)
from homeassistant.helpers.typing import ConfigType

from ..config_validation import VALUE_SCHEMA
from ..const import (
    ATTR_COMMAND_CLASS,
    ATTR_COMMAND_CLASS_NAME,
    ATTR_CURRENT_VALUE,
    ATTR_CURRENT_VALUE_RAW,
    ATTR_ENDPOINT,
    ATTR_NODE_ID,
    ATTR_PREVIOUS_VALUE,
    ATTR_PREVIOUS_VALUE_RAW,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_PROPERTY_KEY_NAME,
    ATTR_PROPERTY_NAME,
    DOMAIN,
    EVENT_VALUE_UPDATED,
)
from ..helpers import async_get_nodes_from_targets, get_device_id
from .trigger_helpers import async_bypass_dynamic_config_validation

# Relative platform type should be <SUBMODULE_NAME>
RELATIVE_PLATFORM_TYPE = f"{__name__.rsplit('.', maxsplit=1)[-1]}"

# Platform type should be <DOMAIN>.<SUBMODULE_NAME>
PLATFORM_TYPE = f"{DOMAIN}.{RELATIVE_PLATFORM_TYPE}"

ATTR_FROM = "from"
ATTR_TO = "to"

_OPTIONS_SCHEMA_DICT = {
    vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_COMMAND_CLASS): vol.In(
        {cc.value: cc.name for cc in CommandClass}
    ),
    vol.Required(ATTR_PROPERTY): vol.Any(vol.Coerce(int), cv.string),
    vol.Optional(ATTR_ENDPOINT): vol.Coerce(int),
    vol.Optional(ATTR_PROPERTY_KEY): vol.Any(vol.Coerce(int), cv.string),
    vol.Optional(ATTR_FROM, default=MATCH_ALL): vol.Any(VALUE_SCHEMA, [VALUE_SCHEMA]),
    vol.Optional(ATTR_TO, default=MATCH_ALL): vol.Any(VALUE_SCHEMA, [VALUE_SCHEMA]),
}

_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            _OPTIONS_SCHEMA_DICT,
            cv.has_at_least_one_key(ATTR_ENTITY_ID, ATTR_DEVICE_ID),
        ),
    },
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = _CONFIG_SCHEMA(config)
    options = config[CONF_OPTIONS]

    if async_bypass_dynamic_config_validation(hass, options):
        return config

    if not async_get_nodes_from_targets(hass, options):
        raise vol.Invalid(
            f"No nodes found for given {ATTR_DEVICE_ID}s or {ATTR_ENTITY_ID}s."
        )
    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    options: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
    *,
    platform_type: str = PLATFORM_TYPE,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    dev_reg = dr.async_get(hass)
    if not async_get_nodes_from_targets(hass, options, dev_reg=dev_reg):
        raise ValueError(
            f"No nodes found for given {ATTR_DEVICE_ID}s or {ATTR_ENTITY_ID}s."
        )

    from_value = options[ATTR_FROM]
    to_value = options[ATTR_TO]
    command_class = options[ATTR_COMMAND_CLASS]
    property_ = options[ATTR_PROPERTY]
    endpoint = options.get(ATTR_ENDPOINT)
    property_key = options.get(ATTR_PROPERTY_KEY)
    unsubs: list[Callable] = []
    job = HassJob(action)

    trigger_data = trigger_info["trigger_data"]

    @callback
    def async_on_value_updated(
        value: Value, device: dr.DeviceEntry, event: dict
    ) -> None:
        """Handle value update."""
        event_value: Value = event["value"]
        if event_value != value:
            return

        # Get previous value and its state value if it exists
        prev_value_raw = event["args"]["prevValue"]
        prev_value = value.metadata.states.get(str(prev_value_raw), prev_value_raw)
        # Get current value and its state value if it exists
        curr_value_raw = event["args"]["newValue"]
        curr_value = value.metadata.states.get(str(curr_value_raw), curr_value_raw)
        # Check from and to values against previous and current values respectively
        for value_to_eval, raw_value_to_eval, match in (
            (prev_value, prev_value_raw, from_value),
            (curr_value, curr_value_raw, to_value),
        ):
            if match not in (MATCH_ALL, value_to_eval, raw_value_to_eval) and not (
                isinstance(match, list)
                and (value_to_eval in match or raw_value_to_eval in match)
            ):
                return

        device_name = device.name_by_user or device.name

        payload = {
            **trigger_data,
            CONF_PLATFORM: platform_type,
            ATTR_DEVICE_ID: device.id,
            ATTR_NODE_ID: value.node.node_id,
            ATTR_COMMAND_CLASS: value.command_class,
            ATTR_COMMAND_CLASS_NAME: value.command_class_name,
            ATTR_PROPERTY: value.property_,
            ATTR_PROPERTY_NAME: value.property_name,
            ATTR_ENDPOINT: endpoint,
            ATTR_PROPERTY_KEY: value.property_key,
            ATTR_PROPERTY_KEY_NAME: value.property_key_name,
            ATTR_PREVIOUS_VALUE: prev_value,
            ATTR_PREVIOUS_VALUE_RAW: prev_value_raw,
            ATTR_CURRENT_VALUE: curr_value,
            ATTR_CURRENT_VALUE_RAW: curr_value_raw,
            "description": f"Z-Wave value {value.value_id} updated on {device_name}",
        }

        hass.async_run_hass_job(job, {"trigger": payload})

    @callback
    def async_remove() -> None:
        """Remove state listeners async."""
        for unsub in unsubs:
            unsub()
        unsubs.clear()

    def _create_zwave_listeners() -> None:
        """Create Z-Wave JS listeners."""
        async_remove()
        # Nodes list can come from different drivers and we will need to listen to
        # server connections for all of them.
        drivers: set[Driver] = set()
        for node in async_get_nodes_from_targets(hass, options, dev_reg=dev_reg):
            driver = node.client.driver
            assert driver is not None  # The node comes from the driver.
            drivers.add(driver)
            device_identifier = get_device_id(driver, node)
            device = dev_reg.async_get_device(identifiers={device_identifier})
            assert device
            value_id = get_value_id_str(
                node, command_class, property_, endpoint, property_key
            )
            value = node.values[value_id]
            # We need to store the current value and device for the callback
            unsubs.append(
                node.on(
                    EVENT_VALUE_UPDATED,
                    functools.partial(async_on_value_updated, value, device),
                )
            )

        unsubs.extend(
            async_dispatcher_connect(
                hass,
                f"{DOMAIN}_{driver.controller.home_id}_connected_to_server",
                _create_zwave_listeners,
            )
            for driver in drivers
        )

    _create_zwave_listeners()

    return async_remove


class ValueUpdatedTrigger(Trigger):
    """Z-Wave JS value updated trigger."""

    _hass: HomeAssistant
    _options: dict[str, Any]

    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return await async_validate_trigger_config(hass, config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        self._hass = hass
        assert config.options is not None
        self._options = config.options

    async def async_attach(
        self,
        action: TriggerActionType,
        trigger_info: TriggerInfo,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""
        return await async_attach_trigger(
            self._hass, self._options, action, trigger_info
        )
