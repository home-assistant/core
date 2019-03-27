"""
Web socket API for Zigbee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import asyncio
import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import async_get_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .core.const import (
    DOMAIN, ATTR_CLUSTER_ID, ATTR_CLUSTER_TYPE, ATTR_ATTRIBUTE, ATTR_VALUE,
    ATTR_MANUFACTURER, ATTR_COMMAND, ATTR_COMMAND_TYPE, ATTR_ARGS, IN, OUT,
    CLIENT_COMMANDS, SERVER_COMMANDS, SERVER, NAME, ATTR_ENDPOINT_ID,
    DATA_ZHA_GATEWAY, DATA_ZHA, MFG_CLUSTER_ID_START)
from .core.helpers import get_matched_clusters, async_is_bindable_target

_LOGGER = logging.getLogger(__name__)

TYPE = 'type'
CLIENT = 'client'
ID = 'id'
RESPONSE = 'response'
DEVICE_INFO = 'device_info'

ATTR_DURATION = 'duration'
ATTR_IEEE_ADDRESS = 'ieee_address'
ATTR_IEEE = 'ieee'
ATTR_SOURCE_IEEE = 'source_ieee'
ATTR_TARGET_IEEE = 'target_ieee'
BIND_REQUEST = 0x0021
UNBIND_REQUEST = 0x0022

SERVICE_PERMIT = 'permit'
SERVICE_REMOVE = 'remove'
SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE = 'set_zigbee_cluster_attribute'
SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND = 'issue_zigbee_cluster_command'
SERVICE_DIRECT_ZIGBEE_BIND = 'issue_direct_zigbee_bind'
SERVICE_DIRECT_ZIGBEE_UNBIND = 'issue_direct_zigbee_unbind'
SERVICE_ZIGBEE_BIND = 'service_zigbee_bind'
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


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required('type'): 'zha/devices/permit'
})
async def websocket_permit_devices(hass, connection, msg):
    """Permit ZHA zigbee devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]

    async def forward_messages(data):
        """Forward events to websocket."""
        connection.send_message(websocket_api.event_message(msg['id'], data))

    remove_dispatcher_function = async_dispatcher_connect(
        hass,
        "zha_gateway_message",
        forward_messages
    )

    @callback
    def async_cleanup() -> None:
        """Remove signal listener and turn off debug mode."""
        zha_gateway.async_disable_debug_mode()
        remove_dispatcher_function()

    connection.subscriptions[msg['id']] = async_cleanup
    zha_gateway.async_enable_debug_mode()
    await zha_gateway.application_controller.permit(60)

    connection.send_result(msg['id'])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices'
})
async def websocket_get_devices(hass, connection, msg):
    """Get ZHA devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ha_device_registry = await async_get_registry(hass)

    devices = []
    for device in zha_gateway.devices.values():
        devices.append(
            async_get_device_info(
                hass, device, ha_device_registry=ha_device_registry
            )
        )
    connection.send_result(msg[ID], devices)


@callback
def async_get_device_info(hass, device, ha_device_registry=None):
    """Get ZHA device."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ret_device = {}
    ret_device.update(device.device_info)
    ret_device['entities'] = [{
        'entity_id': entity_ref.reference_id,
        NAME: entity_ref.device_info[NAME]
    } for entity_ref in zha_gateway.device_registry[device.ieee]]

    if ha_device_registry is not None:
        reg_device = ha_device_registry.async_get_device(
            {(DOMAIN, str(device.ieee))}, set())
        if reg_device is not None:
            ret_device['user_given_name'] = reg_device.name_by_user
            ret_device['device_reg_id'] = reg_device.id
            ret_device['area_id'] = reg_device.area_id
    return ret_device


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices/reconfigure',
    vol.Required(ATTR_IEEE): str
})
async def websocket_reconfigure_node(hass, connection, msg):
    """Reconfigure a ZHA nodes entities by its ieee address."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
    device = zha_gateway.get_device(ieee)
    _LOGGER.debug("Reconfiguring node with ieee_address: %s", ieee)
    hass.async_create_task(device.async_configure())


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices/clusters',
    vol.Required(ATTR_IEEE): str
})
async def websocket_device_clusters(hass, connection, msg):
    """Return a list of device clusters."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
    zha_device = zha_gateway.get_device(ieee)
    response_clusters = []
    if zha_device is not None:
        clusters_by_endpoint = zha_device.async_get_clusters()
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

    connection.send_result(msg[ID], response_clusters)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices/clusters/attributes',
    vol.Required(ATTR_IEEE): str,
    vol.Required(ATTR_ENDPOINT_ID): int,
    vol.Required(ATTR_CLUSTER_ID): int,
    vol.Required(ATTR_CLUSTER_TYPE): str
})
async def websocket_device_cluster_attributes(hass, connection, msg):
    """Return a list of cluster attributes."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
    endpoint_id = msg[ATTR_ENDPOINT_ID]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    cluster_attributes = []
    zha_device = zha_gateway.get_device(ieee)
    attributes = None
    if zha_device is not None:
        attributes = zha_device.async_get_cluster_attributes(
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

    connection.send_result(msg[ID], cluster_attributes)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices/clusters/commands',
    vol.Required(ATTR_IEEE): str,
    vol.Required(ATTR_ENDPOINT_ID): int,
    vol.Required(ATTR_CLUSTER_ID): int,
    vol.Required(ATTR_CLUSTER_TYPE): str
})
async def websocket_device_cluster_commands(hass, connection, msg):
    """Return a list of cluster commands."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    ieee = msg[ATTR_IEEE]
    endpoint_id = msg[ATTR_ENDPOINT_ID]
    zha_device = zha_gateway.get_device(ieee)
    cluster_commands = []
    commands = None
    if zha_device is not None:
        commands = zha_device.async_get_cluster_commands(
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

    connection.send_result(msg[ID], cluster_commands)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices/clusters/attributes/value',
    vol.Required(ATTR_IEEE): str,
    vol.Required(ATTR_ENDPOINT_ID): int,
    vol.Required(ATTR_CLUSTER_ID): int,
    vol.Required(ATTR_CLUSTER_TYPE): str,
    vol.Required(ATTR_ATTRIBUTE): int,
    vol.Optional(ATTR_MANUFACTURER): object,
})
async def websocket_read_zigbee_cluster_attributes(hass, connection, msg):
    """Read zigbee attribute for cluster on zha entity."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
    endpoint_id = msg[ATTR_ENDPOINT_ID]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    attribute = msg[ATTR_ATTRIBUTE]
    manufacturer = msg.get(ATTR_MANUFACTURER) or None
    zha_device = zha_gateway.get_device(ieee)
    if cluster_id >= MFG_CLUSTER_ID_START and manufacturer is None:
        manufacturer = zha_device.manufacturer_code
    success = failure = None
    if zha_device is not None:
        cluster = zha_device.async_get_cluster(
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
    connection.send_result(msg[ID], str(success.get(attribute)))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices/bindable',
    vol.Required(ATTR_IEEE): str,
})
async def websocket_get_bindable_devices(hass, connection, msg):
    """Directly bind devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    source_ieee = msg[ATTR_IEEE]
    source_device = zha_gateway.get_device(source_ieee)
    devices = [
        {
            **device.device_info
        } for device in zha_gateway.devices.values() if
        async_is_bindable_target(source_device, device)
    ]

    _LOGGER.debug("Get bindable devices: %s %s",
                  "{}: [{}]".format(ATTR_SOURCE_IEEE, source_ieee),
                  "{}: [{}]".format('bindable devices:', devices)
                  )

    connection.send_message(websocket_api.result_message(
        msg[ID],
        devices
    ))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices/bind',
    vol.Required(ATTR_SOURCE_IEEE): str,
    vol.Required(ATTR_TARGET_IEEE): str
})
async def websocket_bind_devices(hass, connection, msg):
    """Directly bind devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    source_ieee = msg[ATTR_SOURCE_IEEE]
    target_ieee = msg[ATTR_TARGET_IEEE]
    await async_binding_operation(
        zha_gateway, source_ieee, target_ieee, BIND_REQUEST)
    _LOGGER.info("Issue bind devices: %s %s",
                 "{}: [{}]".format(ATTR_SOURCE_IEEE, source_ieee),
                 "{}: [{}]".format(ATTR_TARGET_IEEE, target_ieee)
                 )


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(TYPE): 'zha/devices/unbind',
    vol.Required(ATTR_SOURCE_IEEE): str,
    vol.Required(ATTR_TARGET_IEEE): str
})
async def websocket_unbind_devices(hass, connection, msg):
    """Remove a direct binding between devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    source_ieee = msg[ATTR_SOURCE_IEEE]
    target_ieee = msg[ATTR_TARGET_IEEE]
    await async_binding_operation(
        zha_gateway, source_ieee, target_ieee, UNBIND_REQUEST)
    _LOGGER.info("Issue unbind devices: %s %s",
                 "{}: [{}]".format(ATTR_SOURCE_IEEE, source_ieee),
                 "{}: [{}]".format(ATTR_TARGET_IEEE, target_ieee)
                 )


async def async_binding_operation(zha_gateway, source_ieee, target_ieee,
                                  operation):
    """Create or remove a direct zigbee binding between 2 devices."""
    from zigpy.zdo import types as zdo_types
    source_device = zha_gateway.get_device(source_ieee)
    target_device = zha_gateway.get_device(target_ieee)

    clusters_to_bind = await get_matched_clusters(source_device,
                                                  target_device)

    bind_tasks = []
    for cluster_pair in clusters_to_bind:
        destination_address = zdo_types.MultiAddress()
        destination_address.addrmode = 3
        destination_address.ieee = target_device.ieee
        destination_address.endpoint = \
            cluster_pair.target_cluster.endpoint.endpoint_id

        zdo = cluster_pair.source_cluster.endpoint.device.zdo

        _LOGGER.debug("processing binding operation for: %s %s %s",
                      "{}: [{}]".format(ATTR_SOURCE_IEEE, source_ieee),
                      "{}: [{}]".format(ATTR_TARGET_IEEE, target_ieee),
                      "{}: {}".format(
                          'cluster',
                          cluster_pair.source_cluster.cluster_id)
                      )
        bind_tasks.append(zdo.request(
            operation,
            source_device.ieee,
            cluster_pair.source_cluster.endpoint.endpoint_id,
            cluster_pair.source_cluster.cluster_id,
            destination_address
        ))
    await asyncio.gather(*bind_tasks)


def async_load_api(hass):
    """Set up the web socket API."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    application_controller = zha_gateway.application_controller

    async def permit(service):
        """Allow devices to join this network."""
        duration = service.data.get(ATTR_DURATION)
        _LOGGER.info("Permitting joins for %ss", duration)
        await application_controller.permit(duration)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_PERMIT, permit, schema=SERVICE_SCHEMAS[SERVICE_PERMIT])

    async def remove(service):
        """Remove a node from the network."""
        from bellows.types import EmberEUI64, uint8_t
        ieee = service.data.get(ATTR_IEEE_ADDRESS)
        ieee = EmberEUI64([uint8_t(p, base=16) for p in ieee.split(':')])
        _LOGGER.info("Removing node %s", ieee)
        await application_controller.remove(ieee)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_REMOVE, remove, schema=SERVICE_SCHEMAS[IEEE_SERVICE])

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
        if cluster_id >= MFG_CLUSTER_ID_START and manufacturer is None:
            manufacturer = zha_device.manufacturer_code
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

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE,
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
        if cluster_id >= MFG_CLUSTER_ID_START and manufacturer is None:
            manufacturer = zha_device.manufacturer_code
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

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND,
        issue_zigbee_cluster_command,
        schema=SERVICE_SCHEMAS[
            SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND
        ])

    websocket_api.async_register_command(hass, websocket_permit_devices)
    websocket_api.async_register_command(hass, websocket_get_devices)
    websocket_api.async_register_command(hass, websocket_reconfigure_node)
    websocket_api.async_register_command(hass, websocket_device_clusters)
    websocket_api.async_register_command(
        hass, websocket_device_cluster_attributes)
    websocket_api.async_register_command(
        hass, websocket_device_cluster_commands)
    websocket_api.async_register_command(
        hass, websocket_read_zigbee_cluster_attributes)
    websocket_api.async_register_command(hass, websocket_get_bindable_devices)
    websocket_api.async_register_command(hass, websocket_bind_devices)
    websocket_api.async_register_command(hass, websocket_unbind_devices)


def async_unload_api(hass):
    """Unload the ZHA API."""
    hass.services.async_remove(DOMAIN, SERVICE_PERMIT)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE)
    hass.services.async_remove(DOMAIN, SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE)
    hass.services.async_remove(DOMAIN, SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND)
