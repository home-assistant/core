"""
Web socket API for Zigbee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from .core.const import (
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

SERVICE_PERMIT = 'permit'
SERVICE_REMOVE = 'remove'
SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE = 'set_zigbee_cluster_attribute'
SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND = 'issue_zigbee_cluster_command'
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


def async_load_api(hass, application_controller, zha_gateway):
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
        entity_ref = zha_gateway.get_entity_reference(entity_id)
        response = None
        if entity_ref is not None:
            response = await entity_ref.zha_device.write_zigbee_attribute(
                list(entity_ref.cluster_listeners.values())[
                    0].cluster.endpoint.endpoint_id,
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
        entity_ref = zha_gateway.get_entity_reference(entity_id)
        zha_device = entity_ref.zha_device
        response = None
        if entity_ref is not None:
            response = await zha_device.issue_cluster_command(
                list(entity_ref.cluster_listeners.values())[
                    0].cluster.endpoint.endpoint_id,
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

    @websocket_api.async_response
    async def websocket_reconfigure_node(hass, connection, msg):
        """Reconfigure a ZHA nodes entities by its ieee address."""
        ieee = msg[ATTR_IEEE]
        device = zha_gateway.get_device(ieee)
        _LOGGER.debug("Reconfiguring node with ieee_address: %s", ieee)
        hass.async_create_task(device.async_configure())

    hass.components.websocket_api.async_register_command(
        WS_RECONFIGURE_NODE, websocket_reconfigure_node,
        SCHEMA_WS_RECONFIGURE_NODE
    )

    @websocket_api.async_response
    async def websocket_entities_by_ieee(hass, connection, msg):
        """Return a dict of all zha entities grouped by ieee."""
        entities_by_ieee = {}
        for ieee, entities in zha_gateway.device_registry.items():
            ieee_string = str(ieee)
            entities_by_ieee[ieee_string] = []
            for entity in entities:
                entities_by_ieee[ieee_string].append({
                    ATTR_ENTITY_ID: entity.reference_id,
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
        entity_ref = zha_gateway.get_entity_reference(entity_id)
        clusters = []
        if entity_ref is not None:
            for listener in entity_ref.cluster_listeners.values():
                cluster = listener.cluster
                in_clusters = cluster.endpoint.in_clusters.values()
                out_clusters = cluster.endpoint.out_clusters.values()
                if cluster in in_clusters:
                    clusters.append({
                        TYPE: IN,
                        ID: cluster.cluster_id,
                        NAME: cluster.__class__.__name__
                    })
                elif cluster in out_clusters:
                    clusters.append({
                        TYPE: OUT,
                        ID: cluster.cluster_id,
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

    @websocket_api.async_response
    async def websocket_entity_cluster_attributes(hass, connection, msg):
        """Return a list of cluster attributes."""
        entity_id = msg[ATTR_ENTITY_ID]
        cluster_id = msg[ATTR_CLUSTER_ID]
        cluster_type = msg[ATTR_CLUSTER_TYPE]
        ieee = msg[ATTR_IEEE]
        cluster_attributes = []
        entity_ref = zha_gateway.get_entity_reference(entity_id)
        device = zha_gateway.get_device(ieee)
        attributes = None
        if entity_ref is not None:
            attributes = await device.get_cluster_attributes(
                list(entity_ref.cluster_listeners.values())[
                    0].cluster.endpoint.endpoint_id,
                cluster_id,
                cluster_type)
            if attributes is not None:
                for attr_id in attributes:
                    cluster_attributes.append(
                        {
                            ID: attr_id,
                            NAME: attributes[attr_id][0]
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

    hass.components.websocket_api.async_register_command(
        WS_ENTITY_CLUSTER_ATTRIBUTES, websocket_entity_cluster_attributes,
        SCHEMA_WS_CLUSTER_ATTRIBUTES
    )

    @websocket_api.async_response
    async def websocket_entity_cluster_commands(hass, connection, msg):
        """Return a list of cluster commands."""
        entity_id = msg[ATTR_ENTITY_ID]
        cluster_id = msg[ATTR_CLUSTER_ID]
        cluster_type = msg[ATTR_CLUSTER_TYPE]
        ieee = msg[ATTR_IEEE]
        entity_ref = zha_gateway.get_entity_reference(entity_id)
        device = zha_gateway.get_device(ieee)
        cluster_commands = []
        commands = None
        if entity_ref is not None:
            commands = await device.get_cluster_commands(
                list(entity_ref.cluster_listeners.values())[
                    0].cluster.endpoint.endpoint_id,
                cluster_id,
                cluster_type)

            if commands is not None:
                for cmd_id in commands[CLIENT_COMMANDS]:
                    cluster_commands.append(
                        {
                            TYPE: CLIENT,
                            ID: cmd_id,
                            NAME: commands[CLIENT_COMMANDS][cmd_id][0]
                        }
                    )
                for cmd_id in commands[SERVER_COMMANDS]:
                    cluster_commands.append(
                        {
                            TYPE: SERVER,
                            ID: cmd_id,
                            NAME: commands[SERVER_COMMANDS][cmd_id][0]
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

    hass.components.websocket_api.async_register_command(
        WS_ENTITY_CLUSTER_COMMANDS, websocket_entity_cluster_commands,
        SCHEMA_WS_CLUSTER_COMMANDS
    )

    @websocket_api.async_response
    async def websocket_read_zigbee_cluster_attributes(hass, connection, msg):
        """Read zigbee attribute for cluster on zha entity."""
        entity_id = msg[ATTR_ENTITY_ID]
        cluster_id = msg[ATTR_CLUSTER_ID]
        cluster_type = msg[ATTR_CLUSTER_TYPE]
        attribute = msg[ATTR_ATTRIBUTE]
        entity_ref = zha_gateway.get_entity_reference(entity_id)
        manufacturer = msg.get(ATTR_MANUFACTURER) or None
        success = failure = None
        clusters = []
        if cluster_type == IN:
            clusters = \
                list(entity_ref.cluster_listeners.values())[
                    0].cluster.endpoint.in_clusters
        else:
            clusters = \
                list(entity_ref.cluster_listeners.values())[
                    0].cluster.endpoint.out_clusters
        cluster = clusters[cluster_id]
        if entity_ref is not None:
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
