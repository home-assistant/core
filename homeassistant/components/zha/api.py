"""
Web socket API for Zigbee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.zha.entities import ZhaDeviceEntity
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from .const import (
    DOMAIN, ATTR_CLUSTER_ID, ATTR_CLUSTER_TYPE, ATTR_ATTRIBUTE, ATTR_VALUE,
    ATTR_MANUFACTURER, ATTR_COMMAND, ATTR_COMMAND_TYPE, ATTR_ARGS, IN, OUT,
    CLIENT_COMMANDS, SERVER_COMMANDS, SERVER)

_LOGGER = logging.getLogger(__name__)

TYPE = 'type'
CLIENT = 'client'
ID = 'id'
NAME = 'name'
RESPONSE = 'response'
DEVICE_INFO = 'device_info'

ATTR_DURATION = 'duration'
ATTR_IEEE_ADDRESS = 'ieee_address'
ATTR_IEEE = 'ieee'
SOURCE_ENTITY_ID = 'source_entity_id'
TARGET_ENTITY_ID = 'target_entity_id'
BIND_REQUEST = 0x0021
UNBIND_REQUEST = 0x0022

SERVICE_PERMIT = 'permit'
SERVICE_REMOVE = 'remove'
SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE = 'set_zigbee_cluster_attribute'
SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND = 'issue_zigbee_cluster_command'
SERVICE_DIRECT_ZIGBEE_BIND = 'issue_direct_zigbee_bind'
SERVICE_DIRECT_ZIGBEE_UNBIND = 'issue_direct_zigbee_unbind'
SERVICE_ZIGBEE_BIND = 'service_zigbee_bind'
ZIGBEE_CLUSTER_SERVICE = 'zigbee_cluster_service'
IEEE_SERVICE = 'ieee_based_service'

SERVICE_SCHEMAS = {
    SERVICE_PERMIT: vol.Schema({
        vol.Optional(ATTR_DURATION, default=60):
            vol.All(vol.Coerce(int), vol.Range(1, 254)),
    }),
    IEEE_SERVICE: vol.Schema({
        vol.Required(ATTR_IEEE_ADDRESS): cv.string,
    }),
    ZIGBEE_CLUSTER_SERVICE: vol.Schema({
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
        vol.Optional(ATTR_CLUSTER_TYPE, default=IN): cv.string
    }),
    SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE: vol.Schema({
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
        vol.Optional(ATTR_CLUSTER_TYPE, default=IN): cv.string,
        vol.Required(ATTR_ATTRIBUTE): cv.positive_int,
        vol.Required(ATTR_VALUE): cv.string,
        vol.Optional(ATTR_MANUFACTURER): cv.positive_int,
    }),
    SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND: vol.Schema({
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
        vol.Optional(ATTR_CLUSTER_TYPE, default=IN): cv.string,
        vol.Required(ATTR_COMMAND): cv.positive_int,
        vol.Required(ATTR_COMMAND_TYPE): cv.string,
        vol.Optional(ATTR_ARGS, default=''): cv.string,
        vol.Optional(ATTR_MANUFACTURER): cv.positive_int,
    }),
    SERVICE_ZIGBEE_BIND: vol.Schema({
        vol.Required(SOURCE_ENTITY_ID): cv.entity_id,
        vol.Required(TARGET_ENTITY_ID): cv.entity_id,
    }),
}

WS_RECONFIGURE_NODE = 'zha/nodes/reconfigure'
SCHEMA_WS_RECONFIGURE_NODE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(TYPE): WS_RECONFIGURE_NODE,
    vol.Required(ATTR_IEEE): str
})

WS_ENTITIES_BY_IEEE = 'zha/entities'
SCHEMA_WS_LIST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(TYPE): WS_ENTITIES_BY_IEEE,
})

WS_ENTITY_CLUSTERS = 'zha/entities/clusters'
SCHEMA_WS_CLUSTERS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(TYPE): WS_ENTITY_CLUSTERS,
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_IEEE): str
})

WS_ENTITY_CLUSTER_ATTRIBUTES = 'zha/entities/clusters/attributes'
SCHEMA_WS_CLUSTER_ATTRIBUTES = \
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
            vol.Required(TYPE): WS_ENTITY_CLUSTER_ATTRIBUTES,
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Required(ATTR_IEEE): str,
            vol.Required(ATTR_CLUSTER_ID): int,
            vol.Required(ATTR_CLUSTER_TYPE): str
        })

WS_READ_CLUSTER_ATTRIBUTE = 'zha/entities/clusters/attributes/value'
SCHEMA_WS_READ_CLUSTER_ATTRIBUTE = \
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
            vol.Required(TYPE): WS_READ_CLUSTER_ATTRIBUTE,
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Required(ATTR_CLUSTER_ID): int,
            vol.Required(ATTR_CLUSTER_TYPE): str,
            vol.Required(ATTR_ATTRIBUTE): int,
            vol.Optional(ATTR_MANUFACTURER): object,
        })

WS_ENTITY_CLUSTER_COMMANDS = 'zha/entities/clusters/commands'
SCHEMA_WS_CLUSTER_COMMANDS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(TYPE): WS_ENTITY_CLUSTER_COMMANDS,
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_IEEE): str,
    vol.Required(ATTR_CLUSTER_ID): int,
    vol.Required(ATTR_CLUSTER_TYPE): str
})


@websocket_api.async_response
async def websocket_entity_cluster_attributes(hass, connection, msg):
    """Return a list of cluster attributes."""
    entity_id = msg[ATTR_ENTITY_ID]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    component = hass.data.get(entity_id.split('.')[0])
    entity = component.get_entity(entity_id)
    cluster_attributes = []
    if entity is not None:
        res = await entity.get_cluster_attributes(cluster_id, cluster_type)
        if res is not None:
            for attr_id in res:
                cluster_attributes.append(
                    {
                        ID: attr_id,
                        NAME: res[attr_id][0]
                    }
                )
    _LOGGER.debug("Requested attributes for: %s %s %s %s",
                  "{}: [{}]".format(ATTR_CLUSTER_ID, cluster_id),
                  "{}: [{}]".format(ATTR_CLUSTER_TYPE, cluster_type),
                  "{}: [{}]".format(ATTR_ENTITY_ID, entity_id),
                  "{}: [{}]".format(RESPONSE, cluster_attributes)
                  )

    connection.send_message(websocket_api.result_message(
        msg[ID],
        cluster_attributes
    ))


@websocket_api.async_response
async def websocket_entity_cluster_commands(hass, connection, msg):
    """Return a list of cluster commands."""
    entity_id = msg[ATTR_ENTITY_ID]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    component = hass.data.get(entity_id.split('.')[0])
    entity = component.get_entity(entity_id)
    cluster_commands = []
    if entity is not None:
        res = await entity.get_cluster_commands(cluster_id, cluster_type)
        if res is not None:
            for cmd_id in res[CLIENT_COMMANDS]:
                cluster_commands.append(
                    {
                        TYPE: CLIENT,
                        ID: cmd_id,
                        NAME: res[CLIENT_COMMANDS][cmd_id][0]
                    }
                )
            for cmd_id in res[SERVER_COMMANDS]:
                cluster_commands.append(
                    {
                        TYPE: SERVER,
                        ID: cmd_id,
                        NAME: res[SERVER_COMMANDS][cmd_id][0]
                    }
                )
    _LOGGER.debug("Requested commands for: %s %s %s %s",
                  "{}: [{}]".format(ATTR_CLUSTER_ID, cluster_id),
                  "{}: [{}]".format(ATTR_CLUSTER_TYPE, cluster_type),
                  "{}: [{}]".format(ATTR_ENTITY_ID, entity_id),
                  "{}: [{}]".format(RESPONSE, cluster_commands)
                  )

    connection.send_message(websocket_api.result_message(
        msg[ID],
        cluster_commands
    ))


@websocket_api.async_response
async def websocket_read_zigbee_cluster_attributes(hass, connection, msg):
    """Read zigbee attribute for cluster on zha entity."""
    entity_id = msg[ATTR_ENTITY_ID]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    attribute = msg[ATTR_ATTRIBUTE]
    component = hass.data.get(entity_id.split('.')[0])
    entity = component.get_entity(entity_id)
    clusters = await entity.get_clusters()
    cluster = clusters[cluster_type][cluster_id]
    manufacturer = msg.get(ATTR_MANUFACTURER) or None
    success = failure = None
    if entity is not None:
        success, failure = await cluster.read_attributes(
            [attribute],
            allow_cache=False,
            only_cache=False,
            manufacturer=manufacturer
        )
    _LOGGER.debug("Read attribute for: %s %s %s %s %s %s %s",
                  "{}: [{}]".format(ATTR_CLUSTER_ID, cluster_id),
                  "{}: [{}]".format(ATTR_CLUSTER_TYPE, cluster_type),
                  "{}: [{}]".format(ATTR_ENTITY_ID, entity_id),
                  "{}: [{}]".format(ATTR_ATTRIBUTE, attribute),
                  "{}: [{}]".format(ATTR_MANUFACTURER, manufacturer),
                  "{}: [{}]".format(RESPONSE, str(success.get(attribute))),
                  "{}: [{}]".format('failure', failure)
                  )
    connection.send_message(websocket_api.result_message(
        msg[ID],
        str(success.get(attribute))
    ))


def async_load_api(hass, application_controller, listener):
    """Set up the web socket API."""
    async def permit(service):
        """Allow devices to join this network."""
        duration = service.data.get(ATTR_DURATION)
        _LOGGER.info("Permitting joins for %ss", duration)
        await application_controller.permit(duration)

    hass.services.async_register(DOMAIN, SERVICE_PERMIT, permit,
                                 schema=SERVICE_SCHEMAS[SERVICE_PERMIT])

    async def remove(service):
        """Remove a node from the network."""
        from bellows.types import EmberEUI64, uint8_t
        ieee = service.data.get(ATTR_IEEE_ADDRESS)
        ieee = EmberEUI64([uint8_t(p, base=16) for p in ieee.split(':')])
        _LOGGER.info("Removing node %s", ieee)
        await application_controller.remove(ieee)

    hass.services.async_register(DOMAIN, SERVICE_REMOVE, remove,
                                 schema=SERVICE_SCHEMAS[IEEE_SERVICE])

    async def set_zigbee_cluster_attributes(service):
        """Set zigbee attribute for cluster on zha entity."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        cluster_id = service.data.get(ATTR_CLUSTER_ID)
        cluster_type = service.data.get(ATTR_CLUSTER_TYPE)
        attribute = service.data.get(ATTR_ATTRIBUTE)
        value = service.data.get(ATTR_VALUE)
        manufacturer = service.data.get(ATTR_MANUFACTURER) or None
        component = hass.data.get(entity_id.split('.')[0])
        entity = component.get_entity(entity_id)
        response = None
        if entity is not None:
            response = await entity.write_zigbe_attribute(
                cluster_id,
                attribute,
                value,
                cluster_type=cluster_type,
                manufacturer=manufacturer
            )
        _LOGGER.debug("Set attribute for: %s %s %s %s %s %s %s",
                      "{}: [{}]".format(ATTR_CLUSTER_ID, cluster_id),
                      "{}: [{}]".format(ATTR_CLUSTER_TYPE, cluster_type),
                      "{}: [{}]".format(ATTR_ENTITY_ID, entity_id),
                      "{}: [{}]".format(ATTR_ATTRIBUTE, attribute),
                      "{}: [{}]".format(ATTR_VALUE, value),
                      "{}: [{}]".format(ATTR_MANUFACTURER, manufacturer),
                      "{}: [{}]".format(RESPONSE, response)
                      )

    hass.services.async_register(DOMAIN, SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE,
                                 set_zigbee_cluster_attributes,
                                 schema=SERVICE_SCHEMAS[
                                     SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE
                                 ])

    async def issue_zigbee_cluster_command(service):
        """Issue command on zigbee cluster on zha entity."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        cluster_id = service.data.get(ATTR_CLUSTER_ID)
        cluster_type = service.data.get(ATTR_CLUSTER_TYPE)
        command = service.data.get(ATTR_COMMAND)
        command_type = service.data.get(ATTR_COMMAND_TYPE)
        args = service.data.get(ATTR_ARGS)
        manufacturer = service.data.get(ATTR_MANUFACTURER) or None
        component = hass.data.get(entity_id.split('.')[0])
        entity = component.get_entity(entity_id)
        response = None
        if entity is not None:
            response = await entity.issue_cluster_command(
                cluster_id,
                command,
                command_type,
                args,
                cluster_type=cluster_type,
                manufacturer=manufacturer
            )
        _LOGGER.debug("Issue command for: %s %s %s %s %s %s %s %s",
                      "{}: [{}]".format(ATTR_CLUSTER_ID, cluster_id),
                      "{}: [{}]".format(ATTR_CLUSTER_TYPE, cluster_type),
                      "{}: [{}]".format(ATTR_ENTITY_ID, entity_id),
                      "{}: [{}]".format(ATTR_COMMAND, command),
                      "{}: [{}]".format(ATTR_COMMAND_TYPE, command_type),
                      "{}: [{}]".format(ATTR_ARGS, args),
                      "{}: [{}]".format(ATTR_MANUFACTURER, manufacturer),
                      "{}: [{}]".format(RESPONSE, response)
                      )

    hass.services.async_register(DOMAIN, SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND,
                                 issue_zigbee_cluster_command,
                                 schema=SERVICE_SCHEMAS[
                                     SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND
                                 ])

    binding_helper = BindingHelper(listener)

    async def issue_direct_zigbee_bind(service):
        """Bind 2 zigbee devices."""
        source_entity_id = service.data.get(SOURCE_ENTITY_ID)
        target_entity_id = service.data.get(TARGET_ENTITY_ID)
        await binding_helper.async_binding_operation(
            source_entity_id, target_entity_id, BIND_REQUEST)
        _LOGGER.info("Issue direct bind: %s %s",
                     "{}: [{}]".format(SOURCE_ENTITY_ID, source_entity_id),
                     "{}: [{}]".format(TARGET_ENTITY_ID, target_entity_id)
                     )

    hass.services.async_register(DOMAIN, SERVICE_DIRECT_ZIGBEE_BIND,
                                 issue_direct_zigbee_bind,
                                 schema=SERVICE_SCHEMAS[
                                     SERVICE_ZIGBEE_BIND
                                 ])

    async def issue_direct_zigbee_unbind(service):
        """Unbind 2 zigbee devices."""
        source_entity_id = service.data.get(SOURCE_ENTITY_ID)
        target_entity_id = service.data.get(TARGET_ENTITY_ID)
        await binding_helper.async_binding_operation(
            source_entity_id, target_entity_id, UNBIND_REQUEST)
        _LOGGER.info("Issue direct unbind: %s %s",
                     "{}: [{}]".format(SOURCE_ENTITY_ID, source_entity_id),
                     "{}: [{}]".format(TARGET_ENTITY_ID, target_entity_id)
                     )

    hass.services.async_register(DOMAIN, SERVICE_DIRECT_ZIGBEE_UNBIND,
                                 issue_direct_zigbee_unbind,
                                 schema=SERVICE_SCHEMAS[
                                     SERVICE_ZIGBEE_BIND
                                 ])

    @websocket_api.async_response
    async def websocket_reconfigure_node(hass, connection, msg):
        """Reconfigure a ZHA nodes entities by its ieee address."""
        ieee = msg[ATTR_IEEE]
        entities = listener.get_entities_for_ieee(ieee)
        _LOGGER.debug("Reconfiguring node with ieee_address: %s", ieee)
        for entity in entities:
            if hasattr(entity, 'async_configure'):
                hass.async_create_task(entity.async_configure())

    hass.components.websocket_api.async_register_command(
        WS_RECONFIGURE_NODE, websocket_reconfigure_node,
        SCHEMA_WS_RECONFIGURE_NODE
    )

    @websocket_api.async_response
    async def websocket_entities_by_ieee(hass, connection, msg):
        """Return a dict of all zha entities grouped by ieee."""
        entities_by_ieee = {}
        for ieee, entities in listener.device_registry.items():
            ieee_string = str(ieee)
            entities_by_ieee[ieee_string] = []
            for entity in entities:
                if not isinstance(entity, ZhaDeviceEntity):
                    entities_by_ieee[ieee_string].append({
                        ATTR_ENTITY_ID: entity.entity_id,
                        DEVICE_INFO: entity.device_info
                    })
        connection.send_message(websocket_api.result_message(
            msg[ID],
            entities_by_ieee
        ))

    hass.components.websocket_api.async_register_command(
        WS_ENTITIES_BY_IEEE, websocket_entities_by_ieee,
        SCHEMA_WS_LIST
    )

    @websocket_api.async_response
    async def websocket_entity_clusters(hass, connection, msg):
        """Return a list of entity clusters."""
        entity_id = msg[ATTR_ENTITY_ID]
        entities = listener.get_entities_for_ieee(msg[ATTR_IEEE])
        entity = next(
            ent for ent in entities if ent.entity_id == entity_id)
        entity_clusters = await entity.get_clusters()
        clusters = []

        for cluster_id, cluster in entity_clusters[IN].items():
            clusters.append({
                TYPE: IN,
                ID: cluster_id,
                NAME: cluster.__class__.__name__
            })
        for cluster_id, cluster in entity_clusters[OUT].items():
            clusters.append({
                TYPE: OUT,
                ID: cluster_id,
                NAME: cluster.__class__.__name__
            })

        connection.send_message(websocket_api.result_message(
            msg[ID],
            clusters
        ))

    hass.components.websocket_api.async_register_command(
        WS_ENTITY_CLUSTERS, websocket_entity_clusters,
        SCHEMA_WS_CLUSTERS
    )

    hass.components.websocket_api.async_register_command(
        WS_ENTITY_CLUSTER_ATTRIBUTES, websocket_entity_cluster_attributes,
        SCHEMA_WS_CLUSTER_ATTRIBUTES
    )

    hass.components.websocket_api.async_register_command(
        WS_ENTITY_CLUSTER_COMMANDS, websocket_entity_cluster_commands,
        SCHEMA_WS_CLUSTER_COMMANDS
    )

    hass.components.websocket_api.async_register_command(
        WS_READ_CLUSTER_ATTRIBUTE, websocket_read_zigbee_cluster_attributes,
        SCHEMA_WS_READ_CLUSTER_ATTRIBUTE
    )


def async_unload_api(hass):
    """Unload the ZHA API."""
    hass.services.async_remove(DOMAIN, SERVICE_PERMIT)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE)
    hass.services.async_remove(DOMAIN, SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE)
    hass.services.async_remove(DOMAIN, SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND)


class ClusterPair:
    """Pair of zigbee clusters."""

    def __init__(self, source_cluster, target_cluster):
        """Initialize the ClusterPair."""
        self._source_cluster = source_cluster
        self._target_cluster = target_cluster

    @property
    def source_cluster(self):
        """Return source cluster."""
        return self._source_cluster

    @property
    def target_cluster(self):
        """Return target cluster."""
        return self._target_cluster


class BindingHelper:
    """Helper class for zigbee binding operations."""

    def __init__(self, application_listener):
        """Initialize the BindingHelper."""
        self._application_listener = application_listener

    async def async_binding_operation(self, source_entity_id, target_entity_id,
                                      operation):
        """Create or remove a direct zigbee binding between 2 devices."""
        from zigpy.zdo import types as zdo_types
        source_entity = self._application_listener.get_entity(source_entity_id)
        target_entity = self._application_listener.get_entity(target_entity_id)
        source_ieee = source_entity.ieee
        target_ieee = target_entity.ieee
        response = []

        clusters_to_bind = await self.get_matched_clusters(
            source_entity,
            target_entity
        )

        for cluster_pair in clusters_to_bind:
            destination_address = zdo_types.MultiAddress()
            destination_address.addrmode = 3
            destination_address.ieee = target_ieee
            destination_address.endpoint = \
                cluster_pair.target_cluster.endpoint.endpoint_id

            zdo = cluster_pair.source_cluster.endpoint.device.zdo

            response.append(await zdo.request(
                operation,
                source_ieee,
                cluster_pair.source_cluster.endpoint.endpoint_id,
                cluster_pair.source_cluster.cluster_id,
                destination_address
            ))
        return response

    async def get_matched_clusters(self, source_entity, target_entity):
        """Get matched input/output cluster pairs for 2 entities."""
        source_clusters = await source_entity.get_clusters()
        target_clusters = await target_entity.get_clusters()
        clusters_to_bind = []

        for cluster in source_clusters[IN]:
            if cluster in target_clusters[OUT]:
                cluster_pair = ClusterPair(
                    source_clusters[IN][cluster],
                    target_clusters[OUT][cluster]
                )
                clusters_to_bind.append(cluster_pair)
        for cluster in source_clusters[OUT]:
            if cluster in target_clusters[IN]:
                cluster_pair = ClusterPair(
                    source_clusters[OUT][cluster],
                    target_clusters[IN][cluster]
                )
                clusters_to_bind.append(cluster_pair)
        return clusters_to_bind
