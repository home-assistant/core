"""Methods and classes related to executing Z-Wave commands."""
from __future__ import annotations

import asyncio
from collections.abc import Generator, Sequence
import logging
import math
from typing import Any, TypeVar

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import SET_VALUE_SUCCESS, CommandClass, CommandStatus
from zwave_js_server.const.command_class.notification import NotificationType
from zwave_js_server.exceptions import FailedZWaveCommand, SetValueFailed
from zwave_js_server.model.endpoint import Endpoint
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import (
    ConfigurationValueFormat,
    ValueDataType,
    get_value_id_str,
)
from zwave_js_server.util.multicast import async_multicast_set_value
from zwave_js_server.util.node import (
    async_bulk_set_partial_config_parameters,
    async_set_config_parameter,
)

from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.group import expand_entity_ids

from . import const
from .config_validation import BITMASK_SCHEMA, VALUE_SCHEMA
from .helpers import (
    async_get_node_from_device_id,
    async_get_node_from_entity_id,
    async_get_nodes_from_area_id,
    async_get_nodes_from_targets,
    get_value_id_from_unique_id,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", ZwaveNode, Endpoint)


def parameter_name_does_not_need_bitmask(
    val: dict[str, int | str | list[str]],
) -> dict[str, int | str | list[str]]:
    """Validate that if a parameter name is provided, bitmask is not as well."""
    if (
        isinstance(val[const.ATTR_CONFIG_PARAMETER], str)
        and const.ATTR_CONFIG_PARAMETER_BITMASK in val
    ):
        raise vol.Invalid(
            "Don't include a bitmask when a parameter name is specified",
            path=[const.ATTR_CONFIG_PARAMETER, const.ATTR_CONFIG_PARAMETER_BITMASK],
        )
    return val


def check_base_2(val: int) -> int:
    """Check if value is a power of 2."""
    if not math.log2(val).is_integer():
        raise vol.Invalid("Value must be a power of 2.")
    return val


def broadcast_command(val: dict[str, Any]) -> dict[str, Any]:
    """Validate that the service call is for a broadcast command."""
    if val.get(const.ATTR_BROADCAST):
        return val
    raise vol.Invalid(
        "Either `broadcast` must be set to True or multiple devices/entities must be "
        "specified"
    )


def get_valid_responses_from_results(
    zwave_objects: Sequence[T], results: Sequence[Any]
) -> Generator[tuple[T, Any], None, None]:
    """Return valid responses from a list of results."""
    for zwave_object, result in zip(zwave_objects, results):
        if not isinstance(result, Exception):
            yield zwave_object, result


def raise_exceptions_from_results(
    zwave_objects: Sequence[T], results: Sequence[Any]
) -> None:
    """Raise list of exceptions from a list of results."""
    errors: Sequence[tuple[T, Any]]
    if errors := [
        tup for tup in zip(zwave_objects, results) if isinstance(tup[1], Exception)
    ]:
        lines = [
            *(
                f"{zwave_object} - {error.__class__.__name__}: {error.args[0]}"
                for zwave_object, error in errors
            )
        ]
        if len(lines) > 1:
            lines.insert(0, f"{len(errors)} error(s):")
        raise HomeAssistantError("\n".join(lines))


async def _async_invoke_cc_api(
    nodes_or_endpoints: set[T],
    command_class: CommandClass,
    method_name: str,
    *args: Any,
) -> None:
    """Invoke the CC API on a node endpoint."""
    nodes_or_endpoints_list = list(nodes_or_endpoints)
    results = await asyncio.gather(
        *(
            node_or_endpoint.async_invoke_cc_api(command_class, method_name, *args)
            for node_or_endpoint in nodes_or_endpoints_list
        ),
        return_exceptions=True,
    )
    for node_or_endpoint, result in get_valid_responses_from_results(
        nodes_or_endpoints_list, results
    ):
        if isinstance(node_or_endpoint, ZwaveNode):
            _LOGGER.info(
                (
                    "Invoked %s CC API method %s on node %s with the following result: "
                    "%s"
                ),
                command_class.name,
                method_name,
                node_or_endpoint,
                result,
            )
        else:
            _LOGGER.info(
                (
                    "Invoked %s CC API method %s on endpoint %s with the following "
                    "result: %s"
                ),
                command_class.name,
                method_name,
                node_or_endpoint,
                result,
            )
    raise_exceptions_from_results(nodes_or_endpoints_list, results)


class ZWaveServices:
    """Class that holds our services (Zwave Commands).

    Services that should be published to hass.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        ent_reg: er.EntityRegistry,
        dev_reg: dr.DeviceRegistry,
    ) -> None:
        """Initialize with hass object."""
        self._hass = hass
        self._ent_reg = ent_reg
        self._dev_reg = dev_reg

    @callback
    def async_register(self) -> None:
        """Register all our services."""

        @callback
        def get_nodes_from_service_data(val: dict[str, Any]) -> dict[str, Any]:
            """Get nodes set from service data."""
            val[const.ATTR_NODES] = async_get_nodes_from_targets(
                self._hass, val, self._ent_reg, self._dev_reg, _LOGGER
            )
            return val

        @callback
        def has_at_least_one_node(val: dict[str, Any]) -> dict[str, Any]:
            """Validate that at least one node is specified."""
            if not val.get(const.ATTR_NODES):
                raise vol.Invalid(f"No {const.DOMAIN} nodes found for given targets")
            return val

        @callback
        def validate_multicast_nodes(val: dict[str, Any]) -> dict[str, Any]:
            """Validate the input nodes for multicast."""
            nodes: set[ZwaveNode] = val[const.ATTR_NODES]
            broadcast: bool = val[const.ATTR_BROADCAST]

            if not broadcast:
                has_at_least_one_node(val)

            # User must specify a node if they are attempting a broadcast and have more
            # than one zwave-js network.
            if (
                broadcast
                and not nodes
                and len(self._hass.config_entries.async_entries(const.DOMAIN)) > 1
            ):
                raise vol.Invalid(
                    "You must include at least one entity or device in the service call"
                )

            first_node = next((node for node in nodes), None)

            if first_node and not all(node.client.driver is not None for node in nodes):
                raise vol.Invalid(f"Driver not ready for all nodes: {nodes}")

            # If any nodes don't have matching home IDs, we can't run the command
            # because we can't multicast across multiple networks
            if (
                first_node
                and first_node.client.driver  # We checked the driver was ready above.
                and any(
                    node.client.driver.controller.home_id
                    != first_node.client.driver.controller.home_id
                    for node in nodes
                    if node.client.driver is not None
                )
            ):
                raise vol.Invalid(
                    "Multicast commands only work on devices in the same network"
                )

            return val

        @callback
        def validate_entities(val: dict[str, Any]) -> dict[str, Any]:
            """Validate entities exist and are from the zwave_js platform."""
            val[ATTR_ENTITY_ID] = expand_entity_ids(self._hass, val[ATTR_ENTITY_ID])
            invalid_entities = []
            for entity_id in val[ATTR_ENTITY_ID]:
                entry = self._ent_reg.async_get(entity_id)
                if entry is None or entry.platform != const.DOMAIN:
                    _LOGGER.info(
                        "Entity %s is not a valid %s entity", entity_id, const.DOMAIN
                    )
                    invalid_entities.append(entity_id)

            # Remove invalid entities
            val[ATTR_ENTITY_ID] = list(set(val[ATTR_ENTITY_ID]) - set(invalid_entities))

            if not val[ATTR_ENTITY_ID]:
                raise vol.Invalid(f"No {const.DOMAIN} entities found in service call")

            return val

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_SET_CONFIG_PARAMETER,
            self.async_set_config_parameter,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Optional(ATTR_AREA_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                        vol.Optional(const.ATTR_ENDPOINT, default=0): vol.Coerce(int),
                        vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Any(
                            vol.Coerce(int), cv.string
                        ),
                        vol.Optional(const.ATTR_CONFIG_PARAMETER_BITMASK): vol.Any(
                            vol.Coerce(int), BITMASK_SCHEMA
                        ),
                        vol.Required(const.ATTR_CONFIG_VALUE): vol.Any(
                            vol.Coerce(int), BITMASK_SCHEMA, cv.string
                        ),
                        vol.Inclusive(const.ATTR_VALUE_SIZE, "raw"): vol.All(
                            vol.Coerce(int), vol.Range(min=1, max=4), check_base_2
                        ),
                        vol.Inclusive(const.ATTR_VALUE_FORMAT, "raw"): vol.Coerce(
                            ConfigurationValueFormat
                        ),
                    },
                    cv.has_at_least_one_key(
                        ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
                    ),
                    cv.has_at_most_one_key(
                        const.ATTR_CONFIG_PARAMETER_BITMASK, const.ATTR_VALUE_SIZE
                    ),
                    parameter_name_does_not_need_bitmask,
                    get_nodes_from_service_data,
                    has_at_least_one_node,
                ),
            ),
        )

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
            self.async_bulk_set_partial_config_parameters,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Optional(ATTR_AREA_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                        vol.Optional(const.ATTR_ENDPOINT, default=0): vol.Coerce(int),
                        vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Coerce(int),
                        vol.Required(const.ATTR_CONFIG_VALUE): vol.Any(
                            vol.Coerce(int),
                            {
                                vol.Any(
                                    vol.Coerce(int), BITMASK_SCHEMA, cv.string
                                ): vol.Any(vol.Coerce(int), BITMASK_SCHEMA, cv.string)
                            },
                        ),
                    },
                    cv.has_at_least_one_key(
                        ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
                    ),
                    get_nodes_from_service_data,
                    has_at_least_one_node,
                ),
            ),
        )

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_REFRESH_VALUE,
            self.async_poll_value,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
                        vol.Optional(
                            const.ATTR_REFRESH_ALL_VALUES, default=False
                        ): cv.boolean,
                    },
                    validate_entities,
                )
            ),
        )

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_SET_VALUE,
            self.async_set_value,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Optional(ATTR_AREA_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                        vol.Required(const.ATTR_COMMAND_CLASS): vol.Coerce(int),
                        vol.Required(const.ATTR_PROPERTY): vol.Any(
                            vol.Coerce(int), str
                        ),
                        vol.Optional(const.ATTR_PROPERTY_KEY): vol.Any(
                            vol.Coerce(int), str
                        ),
                        vol.Optional(const.ATTR_ENDPOINT): vol.Coerce(int),
                        vol.Required(const.ATTR_VALUE): VALUE_SCHEMA,
                        vol.Optional(const.ATTR_WAIT_FOR_RESULT): cv.boolean,
                        vol.Optional(const.ATTR_OPTIONS): {cv.string: VALUE_SCHEMA},
                    },
                    cv.has_at_least_one_key(
                        ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
                    ),
                    get_nodes_from_service_data,
                    has_at_least_one_node,
                ),
            ),
        )

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_MULTICAST_SET_VALUE,
            self.async_multicast_set_value,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Optional(ATTR_AREA_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                        vol.Optional(const.ATTR_BROADCAST, default=False): cv.boolean,
                        vol.Required(const.ATTR_COMMAND_CLASS): vol.Coerce(int),
                        vol.Required(const.ATTR_PROPERTY): vol.Any(
                            vol.Coerce(int), str
                        ),
                        vol.Optional(const.ATTR_PROPERTY_KEY): vol.Any(
                            vol.Coerce(int), str
                        ),
                        vol.Optional(const.ATTR_ENDPOINT): vol.Coerce(int),
                        vol.Required(const.ATTR_VALUE): VALUE_SCHEMA,
                        vol.Optional(const.ATTR_OPTIONS): {cv.string: VALUE_SCHEMA},
                    },
                    vol.Any(
                        cv.has_at_least_one_key(
                            ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
                        ),
                        broadcast_command,
                    ),
                    get_nodes_from_service_data,
                    validate_multicast_nodes,
                ),
            ),
        )

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_PING,
            self.async_ping,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Optional(ATTR_AREA_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                    },
                    cv.has_at_least_one_key(
                        ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
                    ),
                    get_nodes_from_service_data,
                    has_at_least_one_node,
                ),
            ),
        )

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_INVOKE_CC_API,
            self.async_invoke_cc_api,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Optional(ATTR_AREA_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                        vol.Required(const.ATTR_COMMAND_CLASS): vol.All(
                            vol.Coerce(int), vol.Coerce(CommandClass)
                        ),
                        vol.Optional(const.ATTR_ENDPOINT): vol.Coerce(int),
                        vol.Required(const.ATTR_METHOD_NAME): cv.string,
                        vol.Required(const.ATTR_PARAMETERS): list,
                    },
                    cv.has_at_least_one_key(
                        ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
                    ),
                    get_nodes_from_service_data,
                    has_at_least_one_node,
                ),
            ),
        )

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_REFRESH_NOTIFICATIONS,
            self.async_refresh_notifications,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Optional(ATTR_AREA_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                        vol.Required(const.ATTR_NOTIFICATION_TYPE): vol.All(
                            vol.Coerce(int), vol.Coerce(NotificationType)
                        ),
                        vol.Optional(const.ATTR_NOTIFICATION_EVENT): vol.Coerce(int),
                    },
                    cv.has_at_least_one_key(
                        ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
                    ),
                    get_nodes_from_service_data,
                    has_at_least_one_node,
                ),
            ),
        )

    async def async_set_config_parameter(self, service: ServiceCall) -> None:
        """Set a config value on a node."""
        nodes: set[ZwaveNode] = service.data[const.ATTR_NODES]
        endpoint = service.data[const.ATTR_ENDPOINT]
        property_or_property_name = service.data[const.ATTR_CONFIG_PARAMETER]
        property_key = service.data.get(const.ATTR_CONFIG_PARAMETER_BITMASK)
        new_value = service.data[const.ATTR_CONFIG_VALUE]
        value_size = service.data.get(const.ATTR_VALUE_SIZE)
        value_format = service.data.get(const.ATTR_VALUE_FORMAT)

        nodes_without_endpoints: set[ZwaveNode] = set()
        # Remove nodes that don't have the specified endpoint
        for node in nodes:
            if endpoint not in node.endpoints:
                nodes_without_endpoints.add(node)
        nodes = nodes.difference(nodes_without_endpoints)
        if not nodes:
            raise HomeAssistantError(
                "None of the specified nodes have the specified endpoint"
            )
        if nodes_without_endpoints and _LOGGER.isEnabledFor(logging.WARNING):
            _LOGGER.warning(
                (
                    "The following nodes do not have endpoint %x and will be "
                    "skipped: %s"
                ),
                endpoint,
                nodes_without_endpoints,
            )

        # If value_size isn't provided, we will use the utility function which includes
        # additional checks and protections. If it is provided, we will use the
        # node.async_set_raw_config_parameter_value method which calls the
        # Configuration CC set API.
        results = await asyncio.gather(
            *(
                async_set_config_parameter(
                    node,
                    new_value,
                    property_or_property_name,
                    property_key=property_key,
                    endpoint=endpoint,
                )
                if value_size is None
                else node.endpoints[endpoint].async_set_raw_config_parameter_value(
                    new_value,
                    property_or_property_name,
                    property_key=property_key,
                    value_size=value_size,
                    value_format=value_format,
                )
                for node in nodes
            ),
            return_exceptions=True,
        )

        def process_results(
            nodes_or_endpoints_list: list[T], _results: list[Any]
        ) -> None:
            """Process results for given nodes or endpoints."""
            for node_or_endpoint, result in get_valid_responses_from_results(
                nodes_or_endpoints_list, _results
            ):
                zwave_value = result[0]
                cmd_status = result[1]
                if cmd_status.status == CommandStatus.ACCEPTED:
                    msg = "Set configuration parameter %s on Node %s with value %s"
                else:
                    msg = (
                        "Added command to queue to set configuration parameter %s on %s "
                        "with value %s. Parameter will be set when the device wakes up"
                    )
                _LOGGER.info(msg, zwave_value, node_or_endpoint, new_value)
            raise_exceptions_from_results(nodes_or_endpoints_list, _results)

        if value_size is None:
            process_results(list(nodes), results)
        else:
            process_results([node.endpoints[endpoint] for node in nodes], results)

    async def async_bulk_set_partial_config_parameters(
        self, service: ServiceCall
    ) -> None:
        """Bulk set multiple partial config values on a node."""
        nodes: set[ZwaveNode] = service.data[const.ATTR_NODES]
        endpoint = service.data[const.ATTR_ENDPOINT]
        property_ = service.data[const.ATTR_CONFIG_PARAMETER]
        new_value = service.data[const.ATTR_CONFIG_VALUE]

        results = await asyncio.gather(
            *(
                async_bulk_set_partial_config_parameters(
                    node,
                    property_,
                    new_value,
                    endpoint=endpoint,
                )
                for node in nodes
            ),
            return_exceptions=True,
        )

        nodes_list = list(nodes)
        for node, cmd_status in get_valid_responses_from_results(nodes_list, results):
            if cmd_status == CommandStatus.ACCEPTED:
                msg = "Bulk set partials for configuration parameter %s on Node %s"
            else:
                msg = (
                    "Queued command to bulk set partials for configuration parameter "
                    "%s on Node %s"
                )

            _LOGGER.info(msg, property_, node)

        raise_exceptions_from_results(nodes_list, results)

    async def async_poll_value(self, service: ServiceCall) -> None:
        """Poll value on a node."""
        for entity_id in service.data[ATTR_ENTITY_ID]:
            entry = self._ent_reg.async_get(entity_id)
            assert entry  # Schema validation would have failed if we can't do this
            async_dispatcher_send(
                self._hass,
                f"{const.DOMAIN}_{entry.unique_id}_poll_value",
                service.data[const.ATTR_REFRESH_ALL_VALUES],
            )

    async def async_set_value(self, service: ServiceCall) -> None:
        """Set a value on a node."""
        nodes: set[ZwaveNode] = service.data[const.ATTR_NODES]
        command_class: CommandClass = service.data[const.ATTR_COMMAND_CLASS]
        property_: int | str = service.data[const.ATTR_PROPERTY]
        property_key: int | str | None = service.data.get(const.ATTR_PROPERTY_KEY)
        endpoint: int | None = service.data.get(const.ATTR_ENDPOINT)
        new_value = service.data[const.ATTR_VALUE]
        wait_for_result = service.data.get(const.ATTR_WAIT_FOR_RESULT)
        options = service.data.get(const.ATTR_OPTIONS)

        coros = []
        for node in nodes:
            value_id = get_value_id_str(
                node,
                command_class,
                property_,
                endpoint=endpoint,
                property_key=property_key,
            )
            # If value has a string type but the new value is not a string, we need to
            # convert it to one. We use new variable `new_value_` to convert the data
            # so we can preserve the original `new_value` for every node.
            if (
                value_id in node.values
                and node.values[value_id].metadata.type == "string"
                and not isinstance(new_value, str)
            ):
                new_value_ = str(new_value)
            else:
                new_value_ = new_value
            coros.append(
                node.async_set_value(
                    value_id,
                    new_value_,
                    options=options,
                    wait_for_result=wait_for_result,
                )
            )

        results = await asyncio.gather(*coros, return_exceptions=True)
        nodes_list = list(nodes)
        # multiple set_values my fail so we will track the entire list
        set_value_failed_nodes_list: list[ZwaveNode] = []
        set_value_failed_error_list: list[SetValueFailed] = []
        for node_, result in get_valid_responses_from_results(nodes_list, results):
            if result and result.status not in SET_VALUE_SUCCESS:
                # If we failed to set a value, add node to exception list
                set_value_failed_nodes_list.append(node_)
                set_value_failed_error_list.append(
                    SetValueFailed(f"{result.status} {result.message}")
                )

        # Add the exception to the results and the nodes to the node list. No-op if
        # no set value commands failed
        raise_exceptions_from_results(
            (*nodes_list, *set_value_failed_nodes_list),
            (*results, *set_value_failed_error_list),
        )

    async def async_multicast_set_value(self, service: ServiceCall) -> None:
        """Set a value via multicast to multiple nodes."""
        nodes: set[ZwaveNode] = service.data[const.ATTR_NODES]
        broadcast: bool = service.data[const.ATTR_BROADCAST]
        options = service.data.get(const.ATTR_OPTIONS)

        if not broadcast and len(nodes) == 1:
            _LOGGER.info(
                "Passing the zwave_js.multicast_set_value service call to the "
                "zwave_js.set_value service since only one node was targeted"
            )
            await self.async_set_value(service)
            return

        command_class: CommandClass = service.data[const.ATTR_COMMAND_CLASS]
        property_: int | str = service.data[const.ATTR_PROPERTY]
        property_key: int | str | None = service.data.get(const.ATTR_PROPERTY_KEY)
        endpoint: int | None = service.data.get(const.ATTR_ENDPOINT)

        value = ValueDataType(commandClass=command_class, property=property_)
        if property_key is not None:
            value["propertyKey"] = property_key
        if endpoint is not None:
            value["endpoint"] = endpoint

        new_value = service.data[const.ATTR_VALUE]

        # If there are no nodes, we can assume there is only one config entry due to
        # schema validation and can use that to get the client, otherwise we can just
        # get the client from the node.
        client: ZwaveClient
        first_node: ZwaveNode
        try:
            first_node = next(node for node in nodes)
            client = first_node.client
        except StopIteration:
            entry_id = self._hass.config_entries.async_entries(const.DOMAIN)[0].entry_id
            client = self._hass.data[const.DOMAIN][entry_id][const.DATA_CLIENT]
            assert client.driver
            first_node = next(
                node
                for node in client.driver.controller.nodes.values()
                if get_value_id_str(
                    node, command_class, property_, endpoint, property_key
                )
                in node.values
            )

        # If value has a string type but the new value is not a string, we need to
        # convert it to one
        value_id = get_value_id_str(
            first_node, command_class, property_, endpoint, property_key
        )
        if (
            value_id in first_node.values
            and first_node.values[value_id].metadata.type == "string"
            and not isinstance(new_value, str)
        ):
            new_value = str(new_value)

        try:
            result = await async_multicast_set_value(
                client=client,
                new_value=new_value,
                value_data=value,
                nodes=None if broadcast else list(nodes),
                options=options,
            )
        except FailedZWaveCommand as err:
            raise HomeAssistantError("Unable to set value via multicast") from err

        if result.status not in SET_VALUE_SUCCESS:
            raise HomeAssistantError(
                "Unable to set value via multicast"
            ) from SetValueFailed(f"{result.status} {result.message}")

    async def async_ping(self, service: ServiceCall) -> None:
        """Ping node(s)."""
        _LOGGER.warning(
            "This service is deprecated in favor of the ping button entity. Service "
            "calls will still work for now but the service will be removed in a "
            "future release"
        )
        nodes: list[ZwaveNode] = list(service.data[const.ATTR_NODES])
        results = await asyncio.gather(
            *(node.async_ping() for node in nodes), return_exceptions=True
        )
        raise_exceptions_from_results(nodes, results)

    async def async_invoke_cc_api(self, service: ServiceCall) -> None:
        """Invoke a command class API."""
        command_class: CommandClass = service.data[const.ATTR_COMMAND_CLASS]
        method_name: str = service.data[const.ATTR_METHOD_NAME]
        parameters: list[Any] = service.data[const.ATTR_PARAMETERS]

        # If an endpoint is provided, we assume the user wants to call the CC API on
        # that endpoint for all target nodes
        if (endpoint := service.data.get(const.ATTR_ENDPOINT)) is not None:
            await _async_invoke_cc_api(
                {node.endpoints[endpoint] for node in service.data[const.ATTR_NODES]},
                command_class,
                method_name,
                *parameters,
            )
            return

        # If no endpoint is provided, we target endpoint 0 for all device and area
        # nodes and we target the endpoint of the primary value for all entities
        # specified.
        endpoints: set[Endpoint] = set()
        for area_id in service.data.get(ATTR_AREA_ID, []):
            for node in async_get_nodes_from_area_id(
                self._hass, area_id, self._ent_reg, self._dev_reg
            ):
                endpoints.add(node.endpoints[0])

        for device_id in service.data.get(ATTR_DEVICE_ID, []):
            try:
                node = async_get_node_from_device_id(
                    self._hass, device_id, self._dev_reg
                )
            except ValueError as err:
                _LOGGER.warning(err.args[0])
                continue
            endpoints.add(node.endpoints[0])

        for entity_id in service.data.get(ATTR_ENTITY_ID, []):
            if (
                not (entity_entry := self._ent_reg.async_get(entity_id))
                or entity_entry.platform != const.DOMAIN
            ):
                _LOGGER.warning(
                    "Skipping entity %s as it is not a valid %s entity",
                    entity_id,
                    const.DOMAIN,
                )
                continue
            node = async_get_node_from_entity_id(
                self._hass, entity_id, self._ent_reg, self._dev_reg
            )
            if (
                value_id := get_value_id_from_unique_id(entity_entry.unique_id)
            ) is None:
                _LOGGER.warning("Skipping entity %s as it has no value ID", entity_id)
                continue

            endpoint_idx = node.values[value_id].endpoint
            endpoints.add(
                node.endpoints[endpoint_idx if endpoint_idx is not None else 0]
            )

        await _async_invoke_cc_api(endpoints, command_class, method_name, *parameters)

    async def async_refresh_notifications(self, service: ServiceCall) -> None:
        """Refresh notifications on a node."""
        nodes: set[ZwaveNode] = service.data[const.ATTR_NODES]
        notification_type: NotificationType = service.data[const.ATTR_NOTIFICATION_TYPE]
        notification_event: int | None = service.data.get(const.ATTR_NOTIFICATION_EVENT)
        param: dict[str, int] = {"notificationType": notification_type.value}
        if notification_event is not None:
            param["notificationEvent"] = notification_event
        await _async_invoke_cc_api(nodes, CommandClass.NOTIFICATION, "get", param)
