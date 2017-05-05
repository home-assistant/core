"""API class to give info to the Z-Wave panel."""

import logging
import homeassistant.core as ha
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import HTTP_NOT_FOUND
from . import const

_LOGGER = logging.getLogger(__name__)

ZWAVE_NETWORK = 'zwave_network'


class ZWaveNodeGroupView(HomeAssistantView):
    """View to return the nodes group configuration."""

    url = "/api/zwave/groups/{node_id}"
    name = "api:zwave:groups"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve groups of node."""
        from openzwave.group import ZWaveGroup

        hass = request.app['hass']
        network = hass.data.get(ZWAVE_NETWORK)
        _LOGGER.info(network.nodes.get(int(node_id)))
        node = network.nodes.get(int(node_id))
        if node is None:
            return self.json_message('Node not found', HTTP_NOT_FOUND)
        groupdata = node.groups_to_dict()
        groups = {}
        for key in groupdata.keys():
            groupnode = ZWaveGroup(key, network, int(node_id))
            groups[key] = {'associations': groupnode.associations,
                           'association_instances':
                           groupnode.associations_instances,
                           'label': groupnode.label,
                           'max_associations': groupnode.max_associations}
        _LOGGER.info('Groups: %s', groups)
        if groups:
            return self.json(groups)
        else:
            return self.json_message('Node not found', HTTP_NOT_FOUND)


class ZWaveNodeConfigView(HomeAssistantView):
    """View to return the nodes configuration options."""

    url = "/api/zwave/config/{node_id}"
    name = "api:zwave:config"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve configurations of node."""
        hass = request.app['hass']
        network = hass.data.get(ZWAVE_NETWORK)
        node = network.nodes.get(int(node_id))
        if node is None:
            return self.json_message('Node not found', HTTP_NOT_FOUND)
        config = {}
        for value in (
                node.get_values(class_id=const.COMMAND_CLASS_CONFIGURATION)
                .values()):
            config[value.index] = {'label': value.label,
                                   'type': value.type,
                                   'help': value.help,
                                   'data_items': value.data_items,
                                   'data': value.data,
                                   'max': value.max,
                                   'min': value.min}
        _LOGGER.info('Config: %s', config)
        if config:
            return self.json(config)
        else:
            return self.json_message('Node not found', HTTP_NOT_FOUND)


class ZWaveUserCodeView(HomeAssistantView):
    """View to return the nodes usercode configuration."""

    url = "/api/zwave/usercodes/{node_id}"
    name = "api:zwave:usercodes"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve usercodes of node."""
        hass = request.app['hass']
        network = hass.data.get(ZWAVE_NETWORK)
        node = network.nodes.get(int(node_id))
        if node is None:
            return self.json_message('Node not found', HTTP_NOT_FOUND)
        usercodes = {}
        if node.has_command_class(const.COMMAND_CLASS_USER_CODE):
            for value in (
                    node.get_values(class_id=const.COMMAND_CLASS_USER_CODE)
                    .values()):
                if value.genre != const.GENRE_USER:
                    continue
                usercodes[value.index] = {'code': value.data,
                                          'label': value.label,
                                          'length': len(value.data)}
            _LOGGER.info('Usercodes: %s', usercodes)
            if usercodes:
                return self.json(usercodes)
            else:
                return self.json_message('Node does not have usercodes',
                                         HTTP_NOT_FOUND)
        else:
            return self.json_message('Node does not have usercodes',
                                     HTTP_NOT_FOUND)
