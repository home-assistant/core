"""Support for monitoring OctoPrint sensors."""
import logging

import requests

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from . import DOMAIN as COMPONENT_DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "octoprint_notification"
NOTIFICATION_TITLE = "OctoPrint sensor setup error"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available OctoPrint sensors."""
    if discovery_info is None:
        return

    name = discovery_info["name"]
    base_url = discovery_info["base_url"]
    monitored_conditions = discovery_info["sensors"]
    octoprint_api = hass.data[COMPONENT_DOMAIN][base_url]
    tools = octoprint_api.get_tools()

    if "Temperatures" in monitored_conditions:
        if not tools:
            hass.components.persistent_notification.create(
                "Your printer appears to be offline.<br />"
                "If you do not want to have your printer on <br />"
                " at all times, and you would like to monitor <br /> "
                "temperatures, please add <br />"
                "bed and/or number&#95of&#95tools to your configuration <br />"
                "and restart.",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID,
            )

    devices = []
    types = ["actual", "target"]
    for octo_type in monitored_conditions:
        if octo_type == "Temperatures":
            for tool in tools:
                for temp_type in types:
                    new_sensor = OctoPrintSensor(
                        octoprint_api,
                        temp_type,
                        temp_type,
                        name,
                        SENSOR_TYPES[octo_type][3],
                        SENSOR_TYPES[octo_type][0],
                        SENSOR_TYPES[octo_type][1],
                        tool,
                    )
                    devices.append(new_sensor)
        else:
            new_sensor = OctoPrintSensor(
                octoprint_api,
                octo_type,
                SENSOR_TYPES[octo_type][2],
                name,
                SENSOR_TYPES[octo_type][3],
                SENSOR_TYPES[octo_type][0],
                SENSOR_TYPES[octo_type][1],
                None,
                SENSOR_TYPES[octo_type][4],
            )
            devices.append(new_sensor)
    add_entities(devices, True)


class OctoPrintSensor(Entity):
    """Representation of an OctoPrint sensor."""

    def __init__(
        self,
        api,
        condition,
        sensor_type,
        sensor_name,
        unit,
        endpoint,
        group,
        tool=None,
        icon=None,
    ):
        """Initialize a new OctoPrint sensor."""
        self.sensor_name = sensor_name
        if tool is None:
            self._name = f"{sensor_name} {condition}"
        else:
            self._name = "{} {} {} {}".format(sensor_name, condition, tool, "temp")
        self.sensor_type = sensor_type
        self.api = api
        self._state = None
        self._unit_of_measurement = unit
        self.api_endpoint = endpoint
        self.api_group = group
        self.api_tool = tool
        self._icon = icon
        _LOGGER.debug("Created OctoPrint sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        sensor_unit = self.unit_of_measurement
        if sensor_unit in (TEMP_CELSIUS, "%"):
            # API sometimes returns null and not 0
            if self._state is None:
                self._state = 0
            return round(self._state, 2)
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Update state of sensor."""
        try:
            self._state = self.api.update(
                self.sensor_type, self.api_endpoint, self.api_group, self.api_tool
            )
        except requests.exceptions.ConnectionError:
            # Error calling the api, already logged in api.update()
            return

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon
