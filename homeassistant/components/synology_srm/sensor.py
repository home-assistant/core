"""Sensor for Synology SRM routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.synology_srm/
"""
import synology_srm
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

CONF_TRAFFIC_INTERVAL = "traffic_interval"

DEFAULT_NAME = "synology_srm"
DEFAULT_USERNAME = "admin"
DEFAULT_PORT = 8001
DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False

EXTERNALIP_CONDITION = "core.ddns_extip"
TRAFFIC_CONDITION = "core.ngfw_traffic"

POSSIBLE_MONITORED_CONDITIONS = {
    "base.encryption",
    "base.info",
    EXTERNALIP_CONDITION,
    "core.ddns_record",
    "core.system_utilization",
    "core.network_nsm_device",
    TRAFFIC_CONDITION,
    "mesh.network_wanstatus",
    "mesh.network_wifidevice",
    "mesh.system_info",
}

DEFAULT_MONITORED_CONDITIONS = [
    EXTERNALIP_CONDITION,
]

POSSIBLE_TRAFFIC_INTERVAL = {"live", "day", "week", "month"}

DEFAULT_TRAFFIC_INTERVAL = [
    "live",
]

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_TRAFFIC_INTERVAL, default=DEFAULT_TRAFFIC_INTERVAL): vol.All(
            cv.ensure_list, [vol.In(POSSIBLE_TRAFFIC_INTERVAL)]
        ),
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED_CONDITIONS
        ): vol.All(cv.ensure_list, [vol.In(POSSIBLE_MONITORED_CONDITIONS)]),
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Synology SRM Sensor."""
    add_devices([SynologySrm(config)])


class SynologySrm(Entity):
    """This class gets information from a SRM router."""

    def __init__(self, config):
        """Initialize."""
        self.config = config

        self.client = synology_srm.Client(
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            https=config[CONF_SSL],
        )

        if not config[CONF_VERIFY_SSL]:
            self.client.http.disable_https_verify()

        self._state = None

        self._attribs = None

    @property
    def name(self):
        """Sensors name."""
        return self.config.get(CONF_NAME)

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:router-wireless"

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Attributes."""
        return self._attribs

    def update(self):
        """Check the router for various information."""
        monitored_conditions = self.config.get(CONF_MONITORED_CONDITIONS)
        attribs = {}
        for condition in monitored_conditions:
            parts = condition.split(".")
            conditionname = condition.replace(".", "_")
            if condition == TRAFFIC_CONDITION:
                for interval in self.config.get(CONF_TRAFFIC_INTERVAL):
                    attrib = self.client.core.ngfw_traffic(interval=interval)
                    attribs[f"{conditionname}_{interval}"] = attrib
            else:
                attrib = getattr(self.client, parts[0])
                attrib = getattr(attrib, parts[1])()
                attribs[conditionname] = attrib
                if condition == EXTERNALIP_CONDITION:
                    first_wan = next(iter(attrib), None)
                    self._state = first_wan and first_wan["ip"]

        self._attribs = attribs
