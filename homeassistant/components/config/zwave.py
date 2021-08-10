"""Provide configuration end points for Z-Wave."""
from collections import deque
import logging

from aiohttp.web import Response

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.zwave import DEVICE_CONFIG_SCHEMA_ENTRY, const
from homeassistant.const import HTTP_ACCEPTED, HTTP_BAD_REQUEST, HTTP_NOT_FOUND, HTTP_OK
import homeassistant.core as ha
import homeassistant.helpers.config_validation as cv

from . import EditKeyBasedConfigView

_LOGGER = logging.getLogger(__name__)
CONFIG_PATH = "zwave_device_config.yaml"
OZW_LOG_FILENAME = "OZW_Log.txt"


async def async_setup(hass):
    """Set up the Z-Wave config API."""
    hass.http.register_view(
        EditKeyBasedConfigView(
            "zwave",
            "device_config",
            CONFIG_PATH,
            cv.entity_id,
            DEVICE_CONFIG_SCHEMA_ENTRY,
        )
    )
    hass.http.register_view(ZWaveNodeValueView)
    hass.http.register_view(ZWaveNodeGroupView)
    hass.http.register_view(ZWaveNodeConfigView)
    hass.http.register_view(ZWaveUserCodeView)
    hass.http.register_view(ZWaveLogView)
    hass.http.register_view(ZWaveConfigWriteView)
    hass.http.register_view(ZWaveProtectionView)

    return True


class ZWaveLogView(HomeAssistantView):
    """View to read the ZWave log file."""

    url = "/api/zwave/ozwlog"
    name = "api:zwave:ozwlog"

    # pylint: disable=no-self-use
    async def get(self, request):
        """Retrieve the lines from ZWave log."""
        try:
            lines = int(request.query.get("lines", 0))
        except ValueError:
            return Response(text="Invalid datetime", status=HTTP_BAD_REQUEST)

        hass = request.app["hass"]
        response = await hass.async_add_executor_job(self._get_log, hass, lines)

        return Response(text="\n".join(response))

    def _get_log(self, hass, lines):
        """Retrieve the logfile content."""
        logfilepath = hass.config.path(OZW_LOG_FILENAME)
        with open(logfilepath, encoding="utf8") as logfile:
            data = (line.rstrip() for line in logfile)
            if lines == 0:
                loglines = list(data)
            else:
                loglines = deque(data, lines)
        return loglines


class ZWaveConfigWriteView(HomeAssistantView):
    """View to save the ZWave configuration to zwcfg_xxxxx.xml."""

    url = "/api/zwave/saveconfig"
    name = "api:zwave:saveconfig"

    @ha.callback
    def post(self, request):
        """Save cache configuration to zwcfg_xxxxx.xml."""
        hass = request.app["hass"]
        network = hass.data.get(const.DATA_NETWORK)
        if network is None:
            return self.json_message("No Z-Wave network data found", HTTP_NOT_FOUND)
        _LOGGER.info("Z-Wave configuration written to file")
        network.write_config()
        return self.json_message("Z-Wave configuration saved to file", HTTP_OK)


class ZWaveNodeValueView(HomeAssistantView):
    """View to return the node values."""

    url = r"/api/zwave/values/{node_id:\d+}"
    name = "api:zwave:values"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve groups of node."""
        nodeid = int(node_id)
        hass = request.app["hass"]
        values_list = hass.data[const.DATA_ENTITY_VALUES]

        values_data = {}
        # Return a list of values for this node that are used as a
        # primary value for an entity
        for entity_values in values_list:
            if entity_values.primary.node.node_id != nodeid:
                continue

            values_data[entity_values.primary.value_id] = {
                "label": entity_values.primary.label,
                "index": entity_values.primary.index,
                "instance": entity_values.primary.instance,
                "poll_intensity": entity_values.primary.poll_intensity,
            }
        return self.json(values_data)


class ZWaveNodeGroupView(HomeAssistantView):
    """View to return the nodes group configuration."""

    url = r"/api/zwave/groups/{node_id:\d+}"
    name = "api:zwave:groups"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve groups of node."""
        nodeid = int(node_id)
        hass = request.app["hass"]
        network = hass.data.get(const.DATA_NETWORK)
        node = network.nodes.get(nodeid)
        if node is None:
            return self.json_message("Node not found", HTTP_NOT_FOUND)
        groupdata = node.groups
        groups = {}
        for key, value in groupdata.items():
            groups[key] = {
                "associations": value.associations,
                "association_instances": value.associations_instances,
                "label": value.label,
                "max_associations": value.max_associations,
            }
        return self.json(groups)


class ZWaveNodeConfigView(HomeAssistantView):
    """View to return the nodes configuration options."""

    url = r"/api/zwave/config/{node_id:\d+}"
    name = "api:zwave:config"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve configurations of node."""
        nodeid = int(node_id)
        hass = request.app["hass"]
        network = hass.data.get(const.DATA_NETWORK)
        node = network.nodes.get(nodeid)
        if node is None:
            return self.json_message("Node not found", HTTP_NOT_FOUND)
        config = {}
        for value in node.get_values(
            class_id=const.COMMAND_CLASS_CONFIGURATION
        ).values():
            config[value.index] = {
                "label": value.label,
                "type": value.type,
                "help": value.help,
                "data_items": value.data_items,
                "data": value.data,
                "max": value.max,
                "min": value.min,
            }
        return self.json(config)


class ZWaveUserCodeView(HomeAssistantView):
    """View to return the nodes usercode configuration."""

    url = r"/api/zwave/usercodes/{node_id:\d+}"
    name = "api:zwave:usercodes"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve usercodes of node."""
        nodeid = int(node_id)
        hass = request.app["hass"]
        network = hass.data.get(const.DATA_NETWORK)
        node = network.nodes.get(nodeid)
        if node is None:
            return self.json_message("Node not found", HTTP_NOT_FOUND)
        usercodes = {}
        if not node.has_command_class(const.COMMAND_CLASS_USER_CODE):
            return self.json(usercodes)
        for value in node.get_values(class_id=const.COMMAND_CLASS_USER_CODE).values():
            if value.genre != const.GENRE_USER:
                continue
            usercodes[value.index] = {
                "code": value.data,
                "label": value.label,
                "length": len(value.data),
            }
        return self.json(usercodes)


class ZWaveProtectionView(HomeAssistantView):
    """View for the protection commandclass of a node."""

    url = r"/api/zwave/protection/{node_id:\d+}"
    name = "api:zwave:protection"

    async def get(self, request, node_id):
        """Retrieve the protection commandclass options of node."""
        nodeid = int(node_id)
        hass = request.app["hass"]
        network = hass.data.get(const.DATA_NETWORK)

        def _fetch_protection():
            """Get protection data."""
            node = network.nodes.get(nodeid)
            if node is None:
                return self.json_message("Node not found", HTTP_NOT_FOUND)
            protection_options = {}
            if not node.has_command_class(const.COMMAND_CLASS_PROTECTION):
                return self.json(protection_options)
            protections = node.get_protections()
            protection_options = {
                "value_id": f"{list(protections)[0]:d}",
                "selected": node.get_protection_item(list(protections)[0]),
                "options": node.get_protection_items(list(protections)[0]),
            }
            return self.json(protection_options)

        return await hass.async_add_executor_job(_fetch_protection)

    async def post(self, request, node_id):
        """Change the selected option in protection commandclass."""
        nodeid = int(node_id)
        hass = request.app["hass"]
        network = hass.data.get(const.DATA_NETWORK)
        protection_data = await request.json()

        def _set_protection():
            """Set protection data."""
            node = network.nodes.get(nodeid)
            selection = protection_data["selection"]
            value_id = int(protection_data[const.ATTR_VALUE_ID])
            if node is None:
                return self.json_message("Node not found", HTTP_NOT_FOUND)
            if not node.has_command_class(const.COMMAND_CLASS_PROTECTION):
                return self.json_message(
                    "No protection commandclass on this node", HTTP_NOT_FOUND
                )
            state = node.set_protection(value_id, selection)
            if not state:
                return self.json_message(
                    "Protection setting did not complete", HTTP_ACCEPTED
                )
            return self.json_message("Protection setting succsessfully set", HTTP_OK)

        return await hass.async_add_executor_job(_set_protection)
