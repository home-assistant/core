"""Web socket API for OpenZWave."""

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

TYPE = "type"
ID = "id"
OZW_INSTANCE = "ozw_instance"
NODE_ID = "node_id"


class ZWaveWebsocketApi:
    """Class that holds our websocket api commands."""

    def __init__(self, hass, manager):
        """Initialize with both hass and ozwmanager objects."""
        self._hass = hass
        self._manager = manager

    @callback
    def async_register_api(self):
        """Register all of our api endpoints."""
        websocket_api.async_register_command(self._hass, self.websocket_network_status)
        websocket_api.async_register_command(self._hass, self.websocket_node_status)
        websocket_api.async_register_command(self._hass, self.websocket_node_statistics)

    @websocket_api.websocket_command(
        {
            vol.Required(TYPE): "ozw/network_status",
            vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
        }
    )
    def websocket_network_status(self, hass, connection, msg):
        """Get Z-Wave network status."""

        connection.send_result(
            msg[ID],
            {
                "state": self._manager.get_instance(msg[OZW_INSTANCE])
                .get_status()
                .status,
                OZW_INSTANCE: msg[OZW_INSTANCE],
            },
        )

    @websocket_api.websocket_command(
        {
            vol.Required(TYPE): "ozw/node_status",
            vol.Required(NODE_ID): vol.Coerce(int),
            vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
        }
    )
    def websocket_node_status(self, hass, connection, msg):
        """Get the status for a Z-Wave node."""

        node = self._manager.get_instance(msg[OZW_INSTANCE]).get_node(msg[NODE_ID])
        connection.send_result(
            msg[ID],
            {
                "node_query_stage": node.node_query_stage,
                "node_id": node.node_id,
                "is_zwave_plus": node.is_zwave_plus,
                "is_awake": node.is_awake,
                "is_failed": node.is_failed,
                "node_baud_rate": node.node_baud_rate,
                "is_beaming": node.is_beaming,
                "is_flirs": node.is_flirs,
                "is_routing": node.is_routing,
                "is_securityv1": node.is_securityv1,
                "node_basic_string": node.node_basic_string,
                "node_generic_string": node.node_generic_string,
                "node_specific_string": node.node_specific_string,
                "neighbors": node.neighbors,
                OZW_INSTANCE: msg[OZW_INSTANCE],
            },
        )

    @websocket_api.websocket_command(
        {
            vol.Required(TYPE): "ozw/node_statistics",
            vol.Required(NODE_ID): vol.Coerce(int),
            vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
        }
    )
    def websocket_node_statistics(self, hass, connection, msg):
        """Get the statistics for a Z-Wave node."""

        stats = (
            self._manager.get_instance(msg[OZW_INSTANCE])
            .get_node(msg[NODE_ID])
            .get_statistics()
        )
        connection.send_result(
            msg[ID],
            {
                "node_id": msg[NODE_ID],
                "send_count": stats.send_count,
                "sent_failed": stats.sent_failed,
                "retries": stats.retries,
                "last_request_rtt": stats.last_request_rtt,
                "last_response_rtt": stats.last_response_rtt,
                "average_request_rtt": stats.average_request_rtt,
                "average_response_rtt": stats.average_response_rtt,
                "received_packets": stats.received_packets,
                "received_dup_packets": stats.received_dup_packets,
                "received_unsolicited": stats.received_unsolicited,
                OZW_INSTANCE: msg[OZW_INSTANCE],
            },
        )
