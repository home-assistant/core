"""Offer Z-Wave JS value updated listening automation trigger."""

from collections.abc import Callable
import functools
from typing import Any, override

import probatio
from zwave_js_server.const import CommandClass
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.value import Value, get_value_id_str

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_OPTIONS, MATCH_ALL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
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
    LOGGER,
)
from ..helpers import (
    async_bypass_dynamic_config_validation,
    async_get_config_entry_from_node,
    async_get_node_from_device_id,
    async_get_nodes_from_targets,
    get_device_id,
    get_endpoint_indices_from_child_device,
)

# Relative platform type should be <SUBMODULE_NAME>
RELATIVE_PLATFORM_TYPE = f"{__name__.rsplit('.', maxsplit=1)[-1]}"

# Platform type should be <DOMAIN>.<SUBMODULE_NAME>
PLATFORM_TYPE = f"{DOMAIN}.{RELATIVE_PLATFORM_TYPE}"

ATTR_FROM = "from"
ATTR_TO = "to"

_OPTIONS_SCHEMA_DICT = {
    probatio.Optional(ATTR_DEVICE_ID): probatio.All(probatio.EnsureList(), [cv.string]),
    probatio.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    probatio.Required(ATTR_COMMAND_CLASS): probatio.All(
        probatio.Coerce(int), probatio.In({cc.value: cc.name for cc in CommandClass})
    ),
    probatio.Required(ATTR_PROPERTY): probatio.Any(probatio.Coerce(int), cv.string),
    probatio.Optional(ATTR_ENDPOINT): probatio.Coerce(int),
    probatio.Optional(ATTR_PROPERTY_KEY): probatio.Any(probatio.Coerce(int), cv.string),
    probatio.Optional(ATTR_FROM, default=MATCH_ALL): probatio.Any(
        VALUE_SCHEMA, [VALUE_SCHEMA]
    ),
    probatio.Optional(ATTR_TO, default=MATCH_ALL): probatio.Any(
        VALUE_SCHEMA, [VALUE_SCHEMA]
    ),
}

_CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OPTIONS): probatio.All(
            _OPTIONS_SCHEMA_DICT,
            probatio.AtLeastOne(ATTR_ENTITY_ID, ATTR_DEVICE_ID),
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
        raise probatio.Invalid(
            f"No nodes found for given {ATTR_DEVICE_ID}s or {ATTR_ENTITY_ID}s."
        )

    # A child device still resolves to its node, so a child target whose endpoint is
    # missing or not covered is dropped when attaching (it must not listen on an
    # unrelated endpoint of the node). Mirror that filtering here and reject the config
    # only when it would leave no target to attach, so the trigger can't silently do
    # nothing. Mixed configs where another target still attaches stay valid.
    endpoint = options.get(ATTR_ENDPOINT)
    dev_reg = dr.async_get(hass)
    targets_a_child = False
    kept_device_ids: list[str] = []
    for device_id in options.get(ATTR_DEVICE_ID, []):
        if not isinstance(
            device_entry := dev_reg.async_get(device_id), dr.ChildDeviceEntry
        ):
            kept_device_ids.append(device_id)
            continue
        targets_a_child = True
        try:
            node = async_get_node_from_device_id(hass, device_id)
        except ValueError:
            continue
        if endpoint in get_endpoint_indices_from_child_device(device_entry, node):
            kept_device_ids.append(device_id)
    if targets_a_child and not async_get_nodes_from_targets(
        hass, {**options, ATTR_DEVICE_ID: kept_device_ids}
    ):
        raise probatio.Invalid(
            f"Endpoint {endpoint} is not covered by any targeted endpoint child device"
        )
    return config


async def async_attach_trigger(
    hass: HomeAssistant, options: ConfigType, run_action: TriggerActionRunner
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

    @callback
    def async_on_value_updated(
        value_id: str, device: dr.AnyDeviceEntry, event: dict
    ) -> None:
        """Handle value update."""
        event_value: Value = event["value"]
        if event_value.value_id != value_id:
            return

        # Get previous value and its state value if it exists
        prev_value_raw = event["args"]["prevValue"]
        prev_value = event_value.metadata.states.get(
            str(prev_value_raw), prev_value_raw
        )
        # Get current value and its state value if it exists
        curr_value_raw = event["args"]["newValue"]
        curr_value = event_value.metadata.states.get(
            str(curr_value_raw), curr_value_raw
        )
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
        description = f"Z-Wave value {event_value.value_id} updated on {device_name}"
        payload = {
            ATTR_DEVICE_ID: device.id,
            ATTR_NODE_ID: event_value.node.node_id,
            ATTR_COMMAND_CLASS: event_value.command_class,
            ATTR_COMMAND_CLASS_NAME: event_value.command_class_name,
            ATTR_PROPERTY: event_value.property_,
            ATTR_PROPERTY_NAME: event_value.property_name,
            ATTR_ENDPOINT: endpoint,
            ATTR_PROPERTY_KEY: event_value.property_key,
            ATTR_PROPERTY_KEY_NAME: event_value.property_key_name,
            ATTR_PREVIOUS_VALUE: prev_value,
            ATTR_PREVIOUS_VALUE_RAW: prev_value_raw,
            ATTR_CURRENT_VALUE: curr_value,
            ATTR_CURRENT_VALUE_RAW: curr_value_raw,
        }

        run_action(payload, description)

    @callback
    def async_remove() -> None:
        """Remove state listeners async."""
        for unsub in unsubs:
            unsub()
        unsubs.clear()

    @callback
    def _create_zwave_listeners() -> None:
        """Create Z-Wave JS listeners."""
        async_remove()
        # When the trigger explicitly targets an endpoint child device, report that
        # child device in the payload. Node-, entity- and area-based targets keep
        # reporting the node (parent) device, so automations that targeted a value
        # before it moved to a child device are not broken. Child targets whose node
        # can't currently be resolved are skipped (like async_get_nodes_from_targets)
        # so reachable targets still attach. A node collapses to a single listener, so
        # only the child device that covers the configured endpoint is mapped; a child
        # that doesn't cover the configured endpoint is dropped entirely so it doesn't
        # attach a parent listener on an unrelated endpoint. The mapping is keyed by the
        # network-scoped node identifier (home id plus node id), since node ids repeat
        # across networks.
        device_ids: list[str] = []
        child_device_by_node: dict[tuple[str, str], dr.AnyDeviceEntry] = {}
        for device_id in options.get(ATTR_DEVICE_ID, []):
            if not isinstance(
                device_entry := dev_reg.async_get(device_id), dr.ChildDeviceEntry
            ):
                device_ids.append(device_id)
                continue
            try:
                target_node = async_get_node_from_device_id(hass, device_id)
            except ValueError:
                continue
            if endpoint not in get_endpoint_indices_from_child_device(
                device_entry, target_node
            ):
                # Normally rejected by async_validate_trigger_config; this is a fallback
                # for bypassed validation or a child whose endpoints changed since.
                LOGGER.warning(
                    "Z-Wave value updated trigger target %s is an endpoint child "
                    "device that does not cover endpoint %s; dropping this target",
                    device_id,
                    endpoint,
                )
                continue
            assert target_node.client.driver is not None
            child_device_by_node[
                get_device_id(target_node.client.driver, target_node)
            ] = device_entry
            device_ids.append(device_id)
        # Resolve listener nodes from the filtered device targets, keeping the entity and
        # area targets untouched so mixed configurations are not broken.
        targets = {**options, ATTR_DEVICE_ID: device_ids}
        # Nodes list can come from different drivers and we will need to listen to
        # server connections for all of them.
        drivers: set[Driver] = set()
        for node in async_get_nodes_from_targets(hass, targets, dev_reg=dev_reg):
            driver = node.client.driver
            assert driver is not None  # The node comes from the driver.
            drivers.add(driver)
            device_identifier = get_device_id(driver, node)
            if (device := child_device_by_node.get(device_identifier)) is None:
                entry = async_get_config_entry_from_node(hass, node)
                device = dev_reg.async_get_device_by_identifier(
                    device_identifier, entry.entry_id
                )
            assert device
            value_id = get_value_id_str(
                node, command_class, property_, endpoint, property_key
            )
            unsubs.append(
                node.on(
                    EVENT_VALUE_UPDATED,
                    functools.partial(async_on_value_updated, value_id, device),
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

    _options: dict[str, Any]

    @classmethod
    @override
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return await async_validate_trigger_config(hass, config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        assert config.options is not None
        self._options = config.options

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""
        return await async_attach_trigger(self._hass, self._options, run_action)
