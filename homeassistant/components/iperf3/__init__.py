"""Support for Iperf3 network measurement tool."""
from __future__ import annotations

from datetime import timedelta
import logging

import iperf3
import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_MONITORED_CONDITIONS,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    DATA_RATE_MEGABITS_PER_SECOND,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

DOMAIN = "iperf3"
DATA_UPDATED = f"{DOMAIN}_data_updated"

_LOGGER = logging.getLogger(__name__)

CONF_DURATION = "duration"
CONF_PARALLEL = "parallel"
CONF_MANUAL = "manual"

DEFAULT_DURATION = 10
DEFAULT_PORT = 5201
DEFAULT_PARALLEL = 1
DEFAULT_PROTOCOL = "tcp"
DEFAULT_INTERVAL = timedelta(minutes=60)

ATTR_DOWNLOAD = "download"
ATTR_UPLOAD = "upload"
ATTR_VERSION = "Version"
ATTR_HOST = "host"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_DOWNLOAD,
        name=ATTR_DOWNLOAD.capitalize(),
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
    ),
    SensorEntityDescription(
        key=ATTR_UPLOAD,
        name=ATTR_UPLOAD.capitalize(),
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PROTOCOLS = ["tcp", "udp"]

HOST_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_DURATION, default=DEFAULT_DURATION): vol.Range(5, 10),
        vol.Optional(CONF_PARALLEL, default=DEFAULT_PARALLEL): vol.Range(1, 20),
        vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.In(PROTOCOLS),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOSTS): vol.All(cv.ensure_list, [HOST_CONFIG_SCHEMA]),
                vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
                    cv.ensure_list, [vol.In(SENSOR_KEYS)]
                ),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
                vol.Optional(CONF_MANUAL, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_HOST, default=None): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the iperf3 component."""
    hass.data[DOMAIN] = {}

    conf = config[DOMAIN]
    for host in conf[CONF_HOSTS]:
        data = hass.data[DOMAIN][host[CONF_HOST]] = Iperf3Data(hass, host)

        if not conf[CONF_MANUAL]:
            async_track_time_interval(hass, data.update, conf[CONF_SCAN_INTERVAL])

    def update(call: ServiceCall) -> None:
        """Service call to manually update the data."""
        called_host = call.data[ATTR_HOST]
        if called_host in hass.data[DOMAIN]:
            hass.data[DOMAIN][called_host].update()
        else:
            for iperf3_host in hass.data[DOMAIN].values():
                iperf3_host.update()

    hass.services.async_register(DOMAIN, "speedtest", update, schema=SERVICE_SCHEMA)

    hass.async_create_task(
        async_load_platform(
            hass,
            SENSOR_DOMAIN,
            DOMAIN,
            {CONF_MONITORED_CONDITIONS: conf[CONF_MONITORED_CONDITIONS]},
            config,
        )
    )

    return True


class Iperf3Data:
    """Get the latest data from iperf3."""

    def __init__(self, hass, host):
        """Initialize the data object."""
        self._hass = hass
        self._host = host
        self.data = {ATTR_DOWNLOAD: None, ATTR_UPLOAD: None, ATTR_VERSION: None}

    def create_client(self):
        """Create a new iperf3 client to use for measurement."""
        client = iperf3.Client()
        client.duration = self._host[CONF_DURATION]
        client.server_hostname = self._host[CONF_HOST]
        client.port = self._host[CONF_PORT]
        client.num_streams = self._host[CONF_PARALLEL]
        client.protocol = self._host[CONF_PROTOCOL]
        client.verbose = False
        return client

    @property
    def protocol(self):
        """Return the protocol used for this connection."""
        return self._host[CONF_PROTOCOL]

    @property
    def host(self):
        """Return the host connected to."""
        return self._host[CONF_HOST]

    @property
    def port(self):
        """Return the port on the host connected to."""
        return self._host[CONF_PORT]

    def update(self, now=None):
        """Get the latest data from iperf3."""
        if self.protocol == "udp":
            # UDP only have 1 way attribute
            result = self._run_test(ATTR_DOWNLOAD)
            self.data[ATTR_DOWNLOAD] = self.data[ATTR_UPLOAD] = getattr(
                result, "Mbps", None
            )
            self.data[ATTR_VERSION] = getattr(result, "version", None)
        else:
            result = self._run_test(ATTR_DOWNLOAD)
            self.data[ATTR_DOWNLOAD] = getattr(result, "received_Mbps", None)
            self.data[ATTR_VERSION] = getattr(result, "version", None)
            self.data[ATTR_UPLOAD] = getattr(
                self._run_test(ATTR_UPLOAD), "sent_Mbps", None
            )

        dispatcher_send(self._hass, DATA_UPDATED, self.host)

    def _run_test(self, test_type):
        """Run and return the iperf3 data."""
        client = self.create_client()
        client.reverse = test_type == ATTR_DOWNLOAD
        try:
            result = client.run()
        except (AttributeError, OSError, ValueError) as error:
            _LOGGER.error("Iperf3 error: %s", error)
            return None

        if result is not None and hasattr(result, "error") and result.error is not None:
            _LOGGER.error("Iperf3 error: %s", result.error)
            return None

        return result
