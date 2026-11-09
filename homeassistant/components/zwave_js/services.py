"""Methods and classes related to executing Z-Wave commands."""

import asyncio
from collections.abc import Collection, Generator, Sequence
import logging
import math
from typing import Any

import probatio
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import SET_VALUE_SUCCESS, CommandClass, CommandStatus
from zwave_js_server.const.command_class.lock import (
    ATTR_CODE_SLOT,
    ATTR_USERCODE,
    OperationType,
)
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

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.group import expand_entity_ids
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import VolDictType

from . import const
from .config_validation import BITMASK_SCHEMA, VALUE_SCHEMA
from .helpers import (
    DriverNotReadyError,
    async_get_node_from_device_id,
    async_get_node_from_entity_id,
    async_get_nodes_from_area_id,
    async_get_nodes_from_targets,
    get_value_id_from_unique_id,
)
from .lock_helpers import CREDENTIAL_RULE_REVERSE_MAP, USER_TYPE_REVERSE_MAP

_LOGGER = logging.getLogger(__name__)

type _NodeOrEndpointType = ZwaveNode | Endpoint

UNIT16_SCHEMA = probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=65535))

TARGET_VALIDATORS: VolDictType = {
    probatio.Optional(ATTR_AREA_ID): probatio.All(probatio.EnsureList(), [cv.string]),
    probatio.Optional(ATTR_DEVICE_ID): probatio.All(probatio.EnsureList(), [cv.string]),
    probatio.Optional(ATTR_ENTITY_ID): cv.entity_ids,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    _async_register_credential_services(hass)
    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        const.SERVICE_RESET_METER,
        entity_domain=SENSOR_DOMAIN,
        schema={
            probatio.Optional(const.ATTR_METER_TYPE): probatio.Coerce(int),
            probatio.Optional(const.ATTR_VALUE): probatio.Coerce(int),
        },
        func="async_reset_meter",
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        const.SERVICE_GET_LOCK_USERCODE,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Optional(ATTR_CODE_SLOT): probatio.Coerce(int),
        },
        func="async_get_lock_usercode",
        supports_response=SupportsResponse.ONLY,
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        const.SERVICE_SET_LOCK_USERCODE,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_CODE_SLOT): probatio.Coerce(int),
            probatio.Required(ATTR_USERCODE): cv.string,
        },
        func="async_set_lock_usercode",
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        const.SERVICE_CLEAR_LOCK_USERCODE,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_CODE_SLOT): probatio.Coerce(int),
        },
        func="async_clear_lock_usercode",
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        const.SERVICE_SET_LOCK_CONFIGURATION,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(const.ATTR_OPERATION_TYPE): probatio.All(
                cv.string,
                probatio.Upper,
                probatio.In(["TIMED", "CONSTANT"]),
                lambda x: OperationType[x],
            ),
            probatio.Optional(const.ATTR_LOCK_TIMEOUT): UNIT16_SCHEMA,
            probatio.Optional(const.ATTR_AUTO_RELOCK_TIME): UNIT16_SCHEMA,
            probatio.Optional(const.ATTR_HOLD_AND_RELEASE_TIME): UNIT16_SCHEMA,
            probatio.Optional(const.ATTR_TWIST_ASSIST): probatio.Coerce(bool),
            probatio.Optional(const.ATTR_BLOCK_TO_BLOCK): probatio.Coerce(bool),
        },
        func="async_set_lock_configuration",
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_SET_CONFIG_PARAMETER,
        _async_set_config_parameter,
        schema=probatio.Schema(
            probatio.All(
                {
                    **TARGET_VALIDATORS,
                    probatio.Optional(const.ATTR_ENDPOINT, default=0): probatio.Coerce(
                        int
                    ),
                    probatio.Required(const.ATTR_CONFIG_PARAMETER): probatio.Any(
                        probatio.Coerce(int), cv.string
                    ),
                    probatio.Optional(
                        const.ATTR_CONFIG_PARAMETER_BITMASK
                    ): probatio.Any(probatio.Coerce(int), BITMASK_SCHEMA),
                    probatio.Required(const.ATTR_CONFIG_VALUE): probatio.Any(
                        probatio.Coerce(int), BITMASK_SCHEMA, cv.string
                    ),
                    probatio.Inclusive(const.ATTR_VALUE_SIZE, "raw"): probatio.All(
                        probatio.Coerce(int),
                        probatio.Range(min=1, max=4),
                        check_base_2,
                    ),
                    probatio.Inclusive(const.ATTR_VALUE_FORMAT, "raw"): probatio.Coerce(
                        ConfigurationValueFormat
                    ),
                },
                probatio.AtLeastOne(ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID),
                probatio.AtMostOne(
                    const.ATTR_CONFIG_PARAMETER_BITMASK, const.ATTR_VALUE_SIZE
                ),
                parameter_name_does_not_need_bitmask,
            ),
        ),
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS,
        _async_bulk_set_partial_config_parameters,
        schema=probatio.Schema(
            probatio.All(
                {
                    **TARGET_VALIDATORS,
                    probatio.Optional(const.ATTR_ENDPOINT, default=0): probatio.Coerce(
                        int
                    ),
                    probatio.Required(const.ATTR_CONFIG_PARAMETER): probatio.Coerce(
                        int
                    ),
                    probatio.Required(const.ATTR_CONFIG_VALUE): probatio.Any(
                        probatio.Coerce(int),
                        {
                            probatio.Any(
                                probatio.Coerce(int), BITMASK_SCHEMA, cv.string
                            ): probatio.Any(
                                probatio.Coerce(int), BITMASK_SCHEMA, cv.string
                            )
                        },
                    ),
                },
                probatio.AtLeastOne(ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID),
            ),
        ),
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_SET_VALUE,
        _async_set_value,
        schema=probatio.Schema(
            probatio.All(
                {
                    **TARGET_VALIDATORS,
                    probatio.Required(const.ATTR_COMMAND_CLASS): probatio.Coerce(int),
                    probatio.Required(const.ATTR_PROPERTY): probatio.Any(
                        probatio.Coerce(int), str
                    ),
                    probatio.Optional(const.ATTR_PROPERTY_KEY): probatio.Any(
                        probatio.Coerce(int), str
                    ),
                    probatio.Optional(const.ATTR_ENDPOINT): probatio.Coerce(int),
                    probatio.Required(const.ATTR_VALUE): VALUE_SCHEMA,
                    probatio.Optional(const.ATTR_WAIT_FOR_RESULT): cv.boolean,
                    probatio.Optional(const.ATTR_OPTIONS): {cv.string: VALUE_SCHEMA},
                },
                probatio.AtLeastOne(ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID),
            ),
        ),
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_MULTICAST_SET_VALUE,
        _async_multicast_set_value,
        schema=probatio.Schema(
            probatio.All(
                {
                    **TARGET_VALIDATORS,
                    probatio.Optional(const.ATTR_BROADCAST, default=False): cv.boolean,
                    probatio.Required(const.ATTR_COMMAND_CLASS): probatio.Coerce(int),
                    probatio.Required(const.ATTR_PROPERTY): probatio.Any(
                        probatio.Coerce(int), str
                    ),
                    probatio.Optional(const.ATTR_PROPERTY_KEY): probatio.Any(
                        probatio.Coerce(int), str
                    ),
                    probatio.Optional(const.ATTR_ENDPOINT): probatio.Coerce(int),
                    probatio.Required(const.ATTR_VALUE): VALUE_SCHEMA,
                    probatio.Optional(const.ATTR_OPTIONS): {cv.string: VALUE_SCHEMA},
                },
                probatio.Any(
                    probatio.AtLeastOne(ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID),
                    broadcast_command,
                ),
            ),
        ),
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_PING,
        _async_ping,
        schema=probatio.Schema(
            probatio.All(
                TARGET_VALIDATORS,
                probatio.AtLeastOne(ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID),
            ),
        ),
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_INVOKE_CC_API,
        _async_invoke_cc_api,
        schema=probatio.Schema(
            probatio.All(
                {
                    **TARGET_VALIDATORS,
                    probatio.Required(const.ATTR_COMMAND_CLASS): probatio.All(
                        probatio.Coerce(int), probatio.Coerce(CommandClass)
                    ),
                    probatio.Optional(const.ATTR_ENDPOINT): probatio.Coerce(int),
                    probatio.Required(const.ATTR_METHOD_NAME): cv.string,
                    probatio.Required(const.ATTR_PARAMETERS): list,
                },
                probatio.AtLeastOne(ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID),
            ),
        ),
        description_placeholders={
            "api_docs_url": "https://zwave-js.github.io/node-zwave-js/#/api/CCs/index"
        },
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_REFRESH_NOTIFICATIONS,
        _async_refresh_notifications,
        schema=probatio.Schema(
            probatio.All(
                {
                    **TARGET_VALIDATORS,
                    probatio.Required(const.ATTR_NOTIFICATION_TYPE): probatio.All(
                        probatio.Coerce(int), probatio.Coerce(NotificationType)
                    ),
                    probatio.Optional(const.ATTR_NOTIFICATION_EVENT): probatio.Coerce(
                        int
                    ),
                },
                probatio.AtLeastOne(ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID),
            ),
        ),
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_REFRESH_VALUE,
        _async_poll_value,
        schema=probatio.Schema(
            {
                probatio.Required(ATTR_ENTITY_ID): cv.entity_ids,
                probatio.Optional(
                    const.ATTR_REFRESH_ALL_VALUES, default=False
                ): cv.boolean,
            }
        ),
    )


@callback
def _async_register_credential_services(hass: HomeAssistant) -> None:
    """Register lock-entity credential platform services."""
    uint16_id = probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=65535))

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        "set_user",
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Optional(const.ATTR_USER_ID): uint16_id,
            probatio.Optional(const.ATTR_USER_NAME): cv.string,
            probatio.Optional(const.ATTR_USER_TYPE): probatio.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
            probatio.Optional(const.ATTR_CREDENTIAL_RULE): probatio.In(
                CREDENTIAL_RULE_REVERSE_MAP.keys()
            ),
            probatio.Optional(const.ATTR_USER_ACTIVE): cv.boolean,
            probatio.Inclusive(const.ATTR_CREDENTIAL_TYPE, "credential"): probatio.In(
                const.WRITABLE_CREDENTIAL_TYPES
            ),
            probatio.Optional(const.ATTR_CREDENTIAL_SLOT): uint16_id,
            probatio.Inclusive(const.ATTR_CREDENTIAL_DATA, "credential"): cv.string,
        },
        func="async_set_user",
        supports_response=SupportsResponse.ONLY,
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        "delete_user",
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={probatio.Required(const.ATTR_USER_ID): uint16_id},
        func="async_delete_user",
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        "delete_all_users",
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_delete_all_users",
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        "get_credential_capabilities",
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_credential_capabilities",
        supports_response=SupportsResponse.ONLY,
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        "get_users",
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_users",
        supports_response=SupportsResponse.ONLY,
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        "set_credential",
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(const.ATTR_USER_ID): uint16_id,
            probatio.Required(const.ATTR_CREDENTIAL_TYPE): probatio.In(
                const.WRITABLE_CREDENTIAL_TYPES
            ),
            probatio.Required(const.ATTR_CREDENTIAL_DATA): cv.string,
            probatio.Optional(const.ATTR_CREDENTIAL_SLOT): uint16_id,
        },
        func="async_set_credential",
        supports_response=SupportsResponse.ONLY,
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        "delete_credential",
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(const.ATTR_USER_ID): uint16_id,
            probatio.Required(const.ATTR_CREDENTIAL_TYPE): probatio.In(
                const.WRITABLE_CREDENTIAL_TYPES
            ),
            probatio.Required(const.ATTR_CREDENTIAL_SLOT): uint16_id,
        },
        func="async_delete_credential",
    )

    async_register_platform_entity_service(
        hass,
        const.DOMAIN,
        "delete_all_credentials",
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={probatio.Required(const.ATTR_USER_ID): uint16_id},
        func="async_delete_all_credentials",
    )


def parameter_name_does_not_need_bitmask(
    val: dict[str, int | str | list[str]],
) -> dict[str, int | str | list[str]]:
    """Validate that if a parameter name is provided, bitmask is not as well."""
    if (
        isinstance(val[const.ATTR_CONFIG_PARAMETER], str)
        and const.ATTR_CONFIG_PARAMETER_BITMASK in val
    ):
        raise probatio.Invalid(
            "Don't include a bitmask when a parameter name is specified",
            path=[const.ATTR_CONFIG_PARAMETER, const.ATTR_CONFIG_PARAMETER_BITMASK],
        )
    return val


def check_base_2(val: int) -> int:
    """Check if value is a power of 2."""
    if not math.log2(val).is_integer():
        raise probatio.Invalid("Value must be a power of 2.")
    return val


def broadcast_command(val: dict[str, Any]) -> dict[str, Any]:
    """Validate that the service call is for a broadcast command."""
    if val.get(const.ATTR_BROADCAST):
        return val
    raise probatio.Invalid(
        "Either `broadcast` must be set to True or multiple devices/entities must be "
        "specified"
    )


def get_valid_responses_from_results[_T: ZwaveNode | Endpoint](
    zwave_objects: Sequence[_T], results: Sequence[Any]
) -> Generator[tuple[_T, Any]]:
    """Return valid responses from a list of results."""
    for zwave_object, result in zip(zwave_objects, results, strict=False):
        if not isinstance(result, Exception):
            yield zwave_object, result


def raise_exceptions_from_results(
    zwave_objects: Sequence[_NodeOrEndpointType], results: Sequence[Any]
) -> None:
    """Raise list of exceptions from a list of results."""
    errors: Sequence[tuple[_NodeOrEndpointType, Any]]
    if errors := [
        tup
        for tup in zip(zwave_objects, results, strict=True)
        if isinstance(tup[1], Exception)
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


async def _async_call_cc_api(
    nodes_or_endpoints: Collection[_NodeOrEndpointType],
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


@callback
def _async_get_target_nodes(call: ServiceCall) -> set[ZwaveNode]:
    """Get the nodes targeted by the action call."""
    try:
        return async_get_nodes_from_targets(
            call.hass, call.data, logger=_LOGGER, raise_on_driver_not_ready=True
        )
    except DriverNotReadyError as err:
        # Not a validation error, so continue_on_error can tolerate it
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key="driver_not_ready",
        ) from err


@callback
def _async_get_nodes(call: ServiceCall) -> set[ZwaveNode]:
    """Get the nodes targeted by the action call, requiring at least one."""
    if not (nodes := _async_get_target_nodes(call)):
        raise ServiceValidationError(
            translation_domain=const.DOMAIN,
            translation_key="no_nodes_found",
        )
    return nodes


async def _async_set_config_parameter(call: ServiceCall) -> None:
    """Set a config value on a node."""
    nodes = _async_get_nodes(call)
    endpoint = call.data[const.ATTR_ENDPOINT]
    property_or_property_name = call.data[const.ATTR_CONFIG_PARAMETER]
    property_key = call.data.get(const.ATTR_CONFIG_PARAMETER_BITMASK)
    new_value = call.data[const.ATTR_CONFIG_VALUE]
    value_size = call.data.get(const.ATTR_VALUE_SIZE)
    value_format = call.data.get(const.ATTR_VALUE_FORMAT)

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
            "The following nodes do not have endpoint %x and will be skipped: %s",
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
        nodes_or_endpoints_list: Sequence[_NodeOrEndpointType], _results: list[Any]
    ) -> None:
        """Process results for given nodes or endpoints."""
        for node_or_endpoint, result in get_valid_responses_from_results(
            nodes_or_endpoints_list, _results
        ):
            if value_size is None:
                # async_set_config_parameter still returns
                # (Value, SetConfigParameterResult)
                zwave_value = result[0]
                cmd_status = result[1]
            else:
                # async_set_raw_config_parameter_value now
                # returns just SetConfigParameterResult
                cmd_status = result
                zwave_value = f"parameter {property_or_property_name}"

            if cmd_status.status == CommandStatus.ACCEPTED:
                msg = "Set configuration parameter %s on Node %s with value %s"
            else:
                msg = (
                    "Added command to queue to set"
                    " configuration parameter %s on %s "
                    "with value %s. Parameter will be set when the device wakes up"
                )
            _LOGGER.info(msg, zwave_value, node_or_endpoint, new_value)
        raise_exceptions_from_results(nodes_or_endpoints_list, _results)

    if value_size is None:
        process_results(list(nodes), results)
    else:
        process_results([node.endpoints[endpoint] for node in nodes], results)


async def _async_bulk_set_partial_config_parameters(call: ServiceCall) -> None:
    """Bulk set multiple partial config values on a node."""
    nodes = _async_get_nodes(call)
    endpoint = call.data[const.ATTR_ENDPOINT]
    property_ = call.data[const.ATTR_CONFIG_PARAMETER]
    new_value = call.data[const.ATTR_CONFIG_VALUE]

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


async def _async_set_value(call: ServiceCall) -> None:
    """Set a value on a node."""
    await _async_set_value_on_nodes(call, _async_get_nodes(call))


async def _async_set_value_on_nodes(call: ServiceCall, nodes: set[ZwaveNode]) -> None:
    """Set a value on the given nodes."""
    command_class: CommandClass = call.data[const.ATTR_COMMAND_CLASS]
    property_: int | str = call.data[const.ATTR_PROPERTY]
    property_key: int | str | None = call.data.get(const.ATTR_PROPERTY_KEY)
    endpoint: int | None = call.data.get(const.ATTR_ENDPOINT)
    new_value = call.data[const.ATTR_VALUE]
    wait_for_result = call.data.get(const.ATTR_WAIT_FOR_RESULT)
    options = call.data.get(const.ATTR_OPTIONS)

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


@callback
def _async_validate_multicast_nodes(
    call: ServiceCall, nodes: set[ZwaveNode], broadcast: bool
) -> None:
    """Validate the target nodes for multicast."""
    # User must specify a node if they are attempting a broadcast and have more
    # than one zwave-js network.
    if (
        broadcast
        and not nodes
        and len(call.hass.config_entries.async_entries(const.DOMAIN)) > 1
    ):
        raise ServiceValidationError(
            translation_domain=const.DOMAIN,
            translation_key="multicast_broadcast_requires_target",
        )

    first_node = next((node for node in nodes), None)

    if first_node and not all(node.client.driver is not None for node in nodes):
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key="driver_not_ready",
        )

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
        raise ServiceValidationError(
            translation_domain=const.DOMAIN,
            translation_key="multicast_different_networks",
        )


async def _async_multicast_set_value(call: ServiceCall) -> None:
    """Set a value via multicast to multiple nodes."""
    broadcast: bool = call.data[const.ATTR_BROADCAST]
    options = call.data.get(const.ATTR_OPTIONS)
    nodes = _async_get_target_nodes(call) if broadcast else _async_get_nodes(call)
    _async_validate_multicast_nodes(call, nodes, broadcast)

    if not broadcast and len(nodes) == 1:
        _LOGGER.info(
            "Passing the zwave_js.multicast_set_value service call to the "
            "zwave_js.set_value service since only one node was targeted"
        )
        await _async_set_value_on_nodes(call, nodes)
        return

    command_class: CommandClass = call.data[const.ATTR_COMMAND_CLASS]
    property_: int | str = call.data[const.ATTR_PROPERTY]
    property_key: int | str | None = call.data.get(const.ATTR_PROPERTY_KEY)
    endpoint: int | None = call.data.get(const.ATTR_ENDPOINT)

    value = ValueDataType(commandClass=command_class, property=property_)
    if property_key is not None:
        value["propertyKey"] = property_key
    if endpoint is not None:
        value["endpoint"] = endpoint

    new_value = call.data[const.ATTR_VALUE]

    # If there are no nodes, we can assume there is only one config entry due to
    # the check above and can use that to get the client, otherwise we can just
    # get the client from the node.
    client: ZwaveClient
    first_node: ZwaveNode
    try:
        first_node = next(node for node in nodes)
        client = first_node.client
    except StopIteration:
        data = call.hass.config_entries.async_entries(const.DOMAIN)[0].runtime_data
        client = data.client
        assert client.driver
        first_node = next(
            node
            for node in client.driver.controller.nodes.values()
            if get_value_id_str(node, command_class, property_, endpoint, property_key)
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


async def _async_ping(call: ServiceCall) -> None:
    """Ping node(s)."""
    _LOGGER.warning(
        "This service is deprecated in favor of the ping button entity. Service "
        "calls will still work for now but the service will be removed in a "
        "future release"
    )
    nodes = list(_async_get_nodes(call))
    results = await asyncio.gather(
        *(node.async_ping() for node in nodes), return_exceptions=True
    )
    raise_exceptions_from_results(nodes, results)


async def _async_invoke_cc_api(call: ServiceCall) -> None:
    """Invoke a command class API."""
    command_class: CommandClass = call.data[const.ATTR_COMMAND_CLASS]
    method_name: str = call.data[const.ATTR_METHOD_NAME]
    parameters: list[Any] = call.data[const.ATTR_PARAMETERS]
    nodes = _async_get_nodes(call)

    # If an endpoint is provided, we assume the user wants to call the CC API on
    # that endpoint for all target nodes
    if (endpoint := call.data.get(const.ATTR_ENDPOINT)) is not None:
        await _async_call_cc_api(
            {node.endpoints[endpoint] for node in nodes},
            command_class,
            method_name,
            *parameters,
        )
        return

    # If no endpoint is provided, we target endpoint 0 for all device and area
    # nodes and we target the endpoint of the primary value for all entities
    # specified.
    ent_reg = er.async_get(call.hass)
    endpoints: set[Endpoint] = set()
    for area_id in call.data.get(ATTR_AREA_ID, []):
        for node in async_get_nodes_from_area_id(call.hass, area_id, ent_reg):
            endpoints.add(node.endpoints[0])

    for device_id in call.data.get(ATTR_DEVICE_ID, []):
        try:
            node = async_get_node_from_device_id(call.hass, device_id)
        # Invalid targets are skipped with a warning, like invalid entities below
        # pylint: disable-next=home-assistant-action-swallowed-exception
        except ValueError as err:
            _LOGGER.warning(err.args[0])
            continue
        endpoints.add(node.endpoints[0])

    for entity_id in call.data.get(ATTR_ENTITY_ID, []):
        if (
            not (entity_entry := ent_reg.async_get(entity_id))
            or entity_entry.platform != const.DOMAIN
        ):
            _LOGGER.warning(
                "Skipping entity %s as it is not a valid %s entity",
                entity_id,
                const.DOMAIN,
            )
            continue
        node = async_get_node_from_entity_id(call.hass, entity_id, ent_reg)
        if (value_id := get_value_id_from_unique_id(entity_entry.unique_id)) is None:
            _LOGGER.warning("Skipping entity %s as it has no value ID", entity_id)
            continue

        endpoint_idx = node.values[value_id].endpoint
        endpoints.add(node.endpoints[endpoint_idx if endpoint_idx is not None else 0])

    await _async_call_cc_api(endpoints, command_class, method_name, *parameters)


async def _async_refresh_notifications(call: ServiceCall) -> None:
    """Refresh notifications on a node."""
    nodes = _async_get_nodes(call)
    notification_type: NotificationType = call.data[const.ATTR_NOTIFICATION_TYPE]
    notification_event: int | None = call.data.get(const.ATTR_NOTIFICATION_EVENT)
    param: dict[str, int] = {"notificationType": notification_type.value}
    if notification_event is not None:
        param["notificationEvent"] = notification_event
    await _async_call_cc_api(nodes, CommandClass.NOTIFICATION, "get", param)


async def _async_poll_value(call: ServiceCall) -> None:
    """Poll value on a node."""
    ent_reg = er.async_get(call.hass)
    entries: list[er.RegistryEntry] = []
    for entity_id in set(expand_entity_ids(call.hass, call.data[ATTR_ENTITY_ID])):
        entry = ent_reg.async_get(entity_id)
        if entry is None or entry.platform != const.DOMAIN:
            _LOGGER.info("Entity %s is not a valid %s entity", entity_id, const.DOMAIN)
            continue
        entries.append(entry)

    if not entries:
        raise ServiceValidationError(
            translation_domain=const.DOMAIN,
            translation_key="no_entities_found",
        )

    for entry in entries:
        async_dispatcher_send(
            call.hass,
            f"{const.DOMAIN}_{entry.unique_id}_poll_value",
            call.data[const.ATTR_REFRESH_ALL_VALUES],
        )
