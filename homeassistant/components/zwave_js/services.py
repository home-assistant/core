"""Methods and classes related to executing Z-Wave commands and publishing these to hass."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandStatus
from zwave_js_server.exceptions import SetValueFailed
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import get_value_id
from zwave_js_server.util.multicast import async_multicast_set_value
from zwave_js_server.util.node import (
    async_bulk_set_partial_config_parameters,
    async_set_config_parameter,
)

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import EntityRegistry

from . import const
from .helpers import async_get_node_from_device_id, async_get_node_from_entity_id

_LOGGER = logging.getLogger(__name__)


def parameter_name_does_not_need_bitmask(
    val: dict[str, int | str | list[str]]
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


def broadcast_command(val: dict[str, Any]) -> dict[str, Any]:
    """Validate that the service call is for a broadcast command."""
    if val.get(const.ATTR_BROADCAST):
        return val
    raise vol.Invalid(
        "Either `broadcast` must be set to True or multiple devices/entities must be "
        "specified"
    )


# Validates that a bitmask is provided in hex form and converts it to decimal
# int equivalent since that's what the library uses
BITMASK_SCHEMA = vol.All(
    cv.string,
    vol.Lower,
    vol.Match(
        r"^(0x)?[0-9a-f]+$",
        msg="Must provide an integer (e.g. 255) or a bitmask in hex form (e.g. 0xff)",
    ),
    lambda value: int(value, 16),
)

VALUE_SCHEMA = vol.Any(
    bool,
    vol.Coerce(int),
    vol.Coerce(float),
    BITMASK_SCHEMA,
    cv.string,
)


class ZWaveServices:
    """Class that holds our services (Zwave Commands) that should be published to hass."""

    def __init__(
        self, hass: HomeAssistant, ent_reg: EntityRegistry, dev_reg: DeviceRegistry
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
            nodes: set[ZwaveNode] = set()
            for entity_id in val.pop(ATTR_ENTITY_ID, []):
                try:
                    nodes.add(
                        async_get_node_from_entity_id(
                            self._hass, entity_id, self._ent_reg, self._dev_reg
                        )
                    )
                except ValueError as err:
                    const.LOGGER.warning(err.args[0])
            for device_id in val.pop(ATTR_DEVICE_ID, []):
                try:
                    nodes.add(
                        async_get_node_from_device_id(
                            self._hass, device_id, self._dev_reg
                        )
                    )
                except ValueError as err:
                    const.LOGGER.warning(err.args[0])

            val[const.ATTR_NODES] = nodes
            return val

        @callback
        def validate_multicast_nodes(val: dict[str, Any]) -> dict[str, Any]:
            """Validate the input nodes for multicast."""
            nodes: set[ZwaveNode] = val[const.ATTR_NODES]
            broadcast: bool = val[const.ATTR_BROADCAST]

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

            # If any nodes don't have matching home IDs, we can't run the command because
            # we can't multicast across multiple networks
            if first_node and any(
                node.client.driver.controller.home_id
                != first_node.client.driver.controller.home_id
                for node in nodes
            ):
                raise vol.Invalid(
                    "Multicast commands only work on devices in the same network"
                )

            return val

        @callback
        def validate_entities(val: dict[str, Any]) -> dict[str, Any]:
            """Validate entities exist and are from the zwave_js platform."""
            for entity_id in val[ATTR_ENTITY_ID]:
                entry = self._ent_reg.async_get(entity_id)
                if entry is None or entry.platform != const.DOMAIN:
                    raise vol.Invalid(
                        f"Entity {entity_id} is not a valid {const.DOMAIN} entity."
                    )

            return val

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_SET_CONFIG_PARAMETER,
            self.async_set_config_parameter,
            schema=vol.Schema(
                vol.All(
                    {
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                        vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Any(
                            vol.Coerce(int), cv.string
                        ),
                        vol.Optional(const.ATTR_CONFIG_PARAMETER_BITMASK): vol.Any(
                            vol.Coerce(int), BITMASK_SCHEMA
                        ),
                        vol.Required(const.ATTR_CONFIG_VALUE): vol.Any(
                            vol.Coerce(int), BITMASK_SCHEMA, cv.string
                        ),
                    },
                    cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
                    parameter_name_does_not_need_bitmask,
                    get_nodes_from_service_data,
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
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
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
                    cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
                    get_nodes_from_service_data,
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
                    cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
                    get_nodes_from_service_data,
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
                    },
                    vol.Any(
                        cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
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
                        vol.Optional(ATTR_DEVICE_ID): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                    },
                    cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
                    get_nodes_from_service_data,
                ),
            ),
        )

    async def async_set_config_parameter(self, service: ServiceCall) -> None:
        """Set a config value on a node."""
        nodes = service.data[const.ATTR_NODES]
        property_or_property_name = service.data[const.ATTR_CONFIG_PARAMETER]
        property_key = service.data.get(const.ATTR_CONFIG_PARAMETER_BITMASK)
        new_value = service.data[const.ATTR_CONFIG_VALUE]

        for node in nodes:
            zwave_value, cmd_status = await async_set_config_parameter(
                node,
                new_value,
                property_or_property_name,
                property_key=property_key,
            )

            if cmd_status == CommandStatus.ACCEPTED:
                msg = "Set configuration parameter %s on Node %s with value %s"
            else:
                msg = (
                    "Added command to queue to set configuration parameter %s on Node "
                    "%s with value %s. Parameter will be set when the device wakes up"
                )

            _LOGGER.info(msg, zwave_value, node, new_value)

    async def async_bulk_set_partial_config_parameters(
        self, service: ServiceCall
    ) -> None:
        """Bulk set multiple partial config values on a node."""
        nodes = service.data[const.ATTR_NODES]
        property_ = service.data[const.ATTR_CONFIG_PARAMETER]
        new_value = service.data[const.ATTR_CONFIG_VALUE]

        for node in nodes:
            cmd_status = await async_bulk_set_partial_config_parameters(
                node,
                property_,
                new_value,
            )

            if cmd_status == CommandStatus.ACCEPTED:
                msg = "Bulk set partials for configuration parameter %s on Node %s"
            else:
                msg = (
                    "Added command to queue to bulk set partials for configuration "
                    "parameter %s on Node %s"
                )

            _LOGGER.info(msg, property_, node)

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
        nodes = service.data[const.ATTR_NODES]
        command_class = service.data[const.ATTR_COMMAND_CLASS]
        property_ = service.data[const.ATTR_PROPERTY]
        property_key = service.data.get(const.ATTR_PROPERTY_KEY)
        endpoint = service.data.get(const.ATTR_ENDPOINT)
        new_value = service.data[const.ATTR_VALUE]
        wait_for_result = service.data.get(const.ATTR_WAIT_FOR_RESULT)
        options = service.data.get(const.ATTR_OPTIONS)

        for node in nodes:
            success = await node.async_set_value(
                get_value_id(
                    node,
                    command_class,
                    property_,
                    endpoint=endpoint,
                    property_key=property_key,
                ),
                new_value,
                options=options,
                wait_for_result=wait_for_result,
            )

            if success is False:
                raise SetValueFailed(
                    "Unable to set value, refer to "
                    "https://zwave-js.github.io/node-zwave-js/#/api/node?id=setvalue "
                    "for possible reasons"
                )

    async def async_multicast_set_value(self, service: ServiceCall) -> None:
        """Set a value via multicast to multiple nodes."""
        nodes = service.data[const.ATTR_NODES]
        broadcast: bool = service.data[const.ATTR_BROADCAST]

        if not broadcast and len(nodes) == 1:
            const.LOGGER.warning(
                "Passing the zwave_js.multicast_set_value service call to the "
                "zwave_js.set_value service since only one node was targeted"
            )
            await self.async_set_value(service)
            return

        value = {
            "commandClass": service.data[const.ATTR_COMMAND_CLASS],
            "property": service.data[const.ATTR_PROPERTY],
            "propertyKey": service.data.get(const.ATTR_PROPERTY_KEY),
            "endpoint": service.data.get(const.ATTR_ENDPOINT),
        }
        new_value = service.data[const.ATTR_VALUE]

        # If there are no nodes, we can assume there is only one config entry due to
        # schema validation and can use that to get the client, otherwise we can just
        # get the client from the node.
        client: ZwaveClient = None
        first_node = next((node for node in nodes), None)
        if first_node:
            client = first_node.client
        else:
            entry_id = self._hass.config_entries.async_entries(const.DOMAIN)[0].entry_id
            client = self._hass.data[const.DOMAIN][entry_id][const.DATA_CLIENT]

        success = await async_multicast_set_value(
            client,
            new_value,
            {k: v for k, v in value.items() if v is not None},
            None if broadcast else list(nodes),
        )

        if success is False:
            raise SetValueFailed("Unable to set value via multicast")

    async def async_ping(self, service: ServiceCall) -> None:
        """Ping node(s)."""
        nodes: set[ZwaveNode] = service.data[const.ATTR_NODES]
        await asyncio.gather(*(node.async_ping() for node in nodes))
