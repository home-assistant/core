"""
Web socket API for Zigbee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import logging
import voluptuous as vol

from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv
from .core.const import (
    DOMAIN, ATTR_CLUSTER_ID, ATTR_CLUSTER_TYPE, ATTR_ATTRIBUTE, ATTR_VALUE,
    ATTR_MANUFACTURER, ATTR_COMMAND, ATTR_COMMAND_TYPE, ATTR_ARGS, IN, OUT,
    CLIENT_COMMANDS, SERVER_COMMANDS, SERVER, NAME, ATTR_ENDPOINT_ID)

_LOGGER = logging.getLogger(__name__)

TYPE = 'type'
CLIENT = 'client'
ID = 'id'
RESPONSE = 'response'
DEVICE_INFO = 'device_info'

ATTR_DURATION = 'duration'
ATTR_IEEE_ADDRESS = 'ieee_address'
ATTR_IEEE = 'ieee'

SERVICE_PERMIT = 'permit'
SERVICE_REMOVE = 'remove'
SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE = 'set_zigbee_cluster_attribute'
SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND = 'issue_zigbee_cluster_command'
IEEE_SERVICE = 'ieee_based_service'

SERVICE_SCHEMAS = {
    SERVICE_PERMIT: vol.Schema({
        vol.Optional(ATTR_DURATION, default=60):
            vol.All(vol.Coerce(int), vol.Range(1, 254)),
    }),
    IEEE_SERVICE: vol.Schema({
        vol.Required(ATTR_IEEE_ADDRESS): cv.string,
    }),
    SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE: vol.Schema({
        vol.Required(ATTR_IEEE): cv.string,
        vol.Required(ATTR_ENDPOINT_ID): cv.positive_int,
        vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
        vol.Optional(ATTR_CLUSTER_TYPE, default=IN): cv.string,
        vol.Required(ATTR_ATTRIBUTE): cv.positive_int,
        vol.Required(ATTR_VALUE): cv.string,
        vol.Optional(ATTR_MANUFACTURER): cv.positive_int,
    }),
    SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND: vol.Schema({
        vol.Required(ATTR_IEEE): cv.string,
        vol.Required(ATTR_ENDPOINT_ID): cv.positive_int,
        vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
        vol.Optional(ATTR_CLUSTER_TYPE, default=IN): cv.string,
        vol.Required(ATTR_COMMAND): cv.positive_int,
        vol.Required(ATTR_COMMAND_TYPE): cv.string,
        vol.Optional(ATTR_ARGS, default=''): cv.string,
        vol.Optional(ATTR_MANUFACTURER): cv.positive_int,
    }),
}

WS_RECONFIGURE_NODE = 'zha/devices/reconfigure'
SCHEMA_WS_RECONFIGURE_NODE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(TYPE): WS_RECONFIGURE_NODE,
    vol.Required(ATTR_IEEE): str
})

WS_DEVICES = 'zha/devices'
SCHEMA_WS_LIST_DEVICES = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(TYPE): WS_DEVICES,
})

WS_DEVICE_CLUSTERS = 'zha/devices/clusters'
SCHEMA_WS_CLUSTERS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(TYPE): WS_DEVICE_CLUSTERS,
    vol.Required(ATTR_IEEE): str
})

WS_DEVICE_CLUSTER_ATTRIBUTES = 'zha/devices/clusters/attributes'
SCHEMA_WS_CLUSTER_ATTRIBUTES = \
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
            vol.Required(TYPE): WS_DEVICE_CLUSTER_ATTRIBUTES,
            vol.Required(ATTR_IEEE): str,
            vol.Required(ATTR_ENDPOINT_ID): int,
            vol.Required(ATTR_CLUSTER_ID): int,
            vol.Required(ATTR_CLUSTER_TYPE): str
        })

WS_READ_CLUSTER_ATTRIBUTE = 'zha/devices/clusters/attributes/value'
SCHEMA_WS_READ_CLUSTER_ATTRIBUTE = \
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
            vol.Required(TYPE): WS_READ_CLUSTER_ATTRIBUTE,
            vol.Required(ATTR_IEEE): str,
            vol.Required(ATTR_ENDPOINT_ID): int,
            vol.Required(ATTR_CLUSTER_ID): int,
            vol.Required(ATTR_CLUSTER_TYPE): str,
            vol.Required(ATTR_ATTRIBUTE): int,
            vol.Optional(ATTR_MANUFACTURER): object,
        })

WS_DEVICE_CLUSTER_COMMANDS = 'zha/devices/clusters/commands'
SCHEMA_WS_CLUSTER_COMMANDS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required(TYPE): WS_DEVICE_CLUSTER_COMMANDS,
    vol.Required(ATTR_IEEE): str,
    vol.Required(ATTR_ENDPOINT_ID): int,
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
        ieee = service.data.get(ATTR_IEEE)
        endpoint_id = service.data.get(ATTR_ENDPOINT_ID)
        cluster_id = service.data.get(ATTR_CLUSTER_ID)
        cluster_type = service.data.get(ATTR_CLUSTER_TYPE)
        attribute = service.data.get(ATTR_ATTRIBUTE)
        value = service.data.get(ATTR_VALUE)
        manufacturer = service.data.get(ATTR_MANUFACTURER) or None
        zha_device = zha_gateway.get_device(ieee)
        response = None
        if zha_device is not None:
            response = await zha_device.write_zigbee_attribute(
                endpoint_id,
                cluster_id,
                attribute,
                value,
                cluster_type=cluster_type,
                manufacturer=manufacturer
            )
        _LOGGER.debug("Set attribute for: %s %s %s %s %s %s %s",
                      "{}: [{}]".format(ATTR_CLUSTER_ID, cluster_id),
                      "{}: [{}]".format(ATTR_CLUSTER_TYPE, cluster_type),
                      "{}: [{}]".format(ATTR_ENDPOINT_ID, endpoint_id),
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
        ieee = service.data.get(ATTR_IEEE)
        endpoint_id = service.data.get(ATTR_ENDPOINT_ID)
        cluster_id = service.data.get(ATTR_CLUSTER_ID)
        cluster_type = service.data.get(ATTR_CLUSTER_TYPE)
        command = service.data.get(ATTR_COMMAND)
        command_type = service.data.get(ATTR_COMMAND_TYPE)
        args = service.data.get(ATTR_ARGS)
        manufacturer = service.data.get(ATTR_MANUFACTURER) or None
        zha_device = zha_gateway.get_device(ieee)
        response = None
        if zha_device is not None:
            response = await zha_device.issue_cluster_command(
                endpoint_id,
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
                      "{}: [{}]".format(ATTR_ENDPOINT_ID, endpoint_id),
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
    async def websocket_get_devices(hass, connection, msg):
        """Get ZHA devices."""
        devices = [
            {
                **device.device_info,
                'entities': [{
                    'entity_id': entity_ref.reference_id,
                    NAME: entity_ref.device_info[NAME]
                } for entity_ref in zha_gateway.device_registry[device.ieee]]
            } for device in zha_gateway.devices.values()
        ]

        connection.send_message(websocket_api.result_message(
            msg[ID],
            devices
        ))

    hass.components.websocket_api.async_register_command(
        WS_DEVICES, websocket_get_devices,
        SCHEMA_WS_LIST_DEVICES
    )

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
    async def websocket_device_clusters(hass, connection, msg):
        """Return a list of device clusters."""
        ieee = msg[ATTR_IEEE]
        zha_device = zha_gateway.get_device(ieee)
        response_clusters = []
        if zha_device is not None:
            clusters_by_endpoint = await zha_device.get_clusters()
            for ep_id, clusters in clusters_by_endpoint.items():
                for c_id, cluster in clusters[IN].items():
                    response_clusters.append({
                        TYPE: IN,
                        ID: c_id,
                        NAME: cluster.__class__.__name__,
                        'endpoint_id': ep_id
                    })
                for c_id, cluster in clusters[OUT].items():
                    response_clusters.append({
                        TYPE: OUT,
                        ID: c_id,
                        NAME: cluster.__class__.__name__,
                        'endpoint_id': ep_id
                    })

        connection.send_message(websocket_api.result_message(
            msg[ID],
            response_clusters
        ))

    hass.components.websocket_api.async_register_command(
        WS_DEVICE_CLUSTERS, websocket_device_clusters,
        SCHEMA_WS_CLUSTERS
    )

    @websocket_api.async_response
    async def websocket_device_cluster_attributes(hass, connection, msg):
        """Return a list of cluster attributes."""
        ieee = msg[ATTR_IEEE]
        endpoint_id = msg[ATTR_ENDPOINT_ID]
        cluster_id = msg[ATTR_CLUSTER_ID]
        cluster_type = msg[ATTR_CLUSTER_TYPE]
        cluster_attributes = []
        zha_device = zha_gateway.get_device(ieee)
        attributes = None
        if zha_device is not None:
            attributes = await zha_device.get_cluster_attributes(
                endpoint_id,
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
                      "{}: [{}]".format(ATTR_ENDPOINT_ID, endpoint_id),
                      "{}: [{}]".format(RESPONSE, cluster_attributes)
                      )

        connection.send_message(websocket_api.result_message(
            msg[ID],
            cluster_attributes
        ))

    hass.components.websocket_api.async_register_command(
        WS_DEVICE_CLUSTER_ATTRIBUTES, websocket_device_cluster_attributes,
        SCHEMA_WS_CLUSTER_ATTRIBUTES
    )

    @websocket_api.async_response
    async def websocket_device_cluster_commands(hass, connection, msg):
        """Return a list of cluster commands."""
        cluster_id = msg[ATTR_CLUSTER_ID]
        cluster_type = msg[ATTR_CLUSTER_TYPE]
        ieee = msg[ATTR_IEEE]
        endpoint_id = msg[ATTR_ENDPOINT_ID]
        zha_device = zha_gateway.get_device(ieee)
        cluster_commands = []
        commands = None
        if zha_device is not None:
            commands = await zha_device.get_cluster_commands(
                endpoint_id,
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
                      "{}: [{}]".format(ATTR_ENDPOINT_ID, endpoint_id),
                      "{}: [{}]".format(RESPONSE, cluster_commands)
                      )

        connection.send_message(websocket_api.result_message(
            msg[ID],
            cluster_commands
        ))

    hass.components.websocket_api.async_register_command(
        WS_DEVICE_CLUSTER_COMMANDS, websocket_device_cluster_commands,
        SCHEMA_WS_CLUSTER_COMMANDS
    )

    @websocket_api.async_response
    async def websocket_read_zigbee_cluster_attributes(hass, connection, msg):
        """Read zigbee attribute for cluster on zha entity."""
        ieee = msg[ATTR_IEEE]
        endpoint_id = msg[ATTR_ENDPOINT_ID]
        cluster_id = msg[ATTR_CLUSTER_ID]
        cluster_type = msg[ATTR_CLUSTER_TYPE]
        attribute = msg[ATTR_ATTRIBUTE]
        manufacturer = msg.get(ATTR_MANUFACTURER) or None
        zha_device = zha_gateway.get_device(ieee)
        success = failure = None
        if zha_device is not None:
            cluster = await zha_device.get_cluster(
                endpoint_id, cluster_id, cluster_type=cluster_type)
            success, failure = await cluster.read_attributes(
                [attribute],
                allow_cache=False,
                only_cache=False,
                manufacturer=manufacturer
            )
        _LOGGER.debug("Read attribute for: %s %s %s %s %s %s %s",
                      "{}: [{}]".format(ATTR_CLUSTER_ID, cluster_id),
                      "{}: [{}]".format(ATTR_CLUSTER_TYPE, cluster_type),
                      "{}: [{}]".format(ATTR_ENDPOINT_ID, endpoint_id),
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
