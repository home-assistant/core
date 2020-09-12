"""Tracks the latency of a host by sending ICMP echo requests (ping)."""
import asyncio
from datetime import timedelta
from functools import partial
import logging
import re
import sys
from typing import Any, Dict

from icmplib import SocketPermissionError, ping as icmp_ping
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import setup_reload_service

from . import DOMAIN, PLATFORMS, async_get_next_ping_id
from .const import PING_TIMEOUT

_LOGGER = logging.getLogger(__name__)


ATTR_ROUND_TRIP_TIME_AVG = "round_trip_time_avg"
ATTR_ROUND_TRIP_TIME_MAX = "round_trip_time_max"
ATTR_ROUND_TRIP_TIME_MDEV = "round_trip_time_mdev"
ATTR_ROUND_TRIP_TIME_MIN = "round_trip_time_min"

CONF_PING_COUNT = "count"

DEFAULT_NAME = "Ping"
DEFAULT_PING_COUNT = 5

SCAN_INTERVAL = timedelta(minutes=5)

PARALLEL_UPDATES = 0

PING_MATCHER = re.compile(
    r"(?P<min>\d+.\d+)\/(?P<avg>\d+.\d+)\/(?P<max>\d+.\d+)\/(?P<mdev>\d+.\d+)"
)

PING_MATCHER_BUSYBOX = re.compile(
    r"(?P<min>\d+.\d+)\/(?P<avg>\d+.\d+)\/(?P<max>\d+.\d+)"
)

WIN32_PING_MATCHER = re.compile(r"(?P<min>\d+)ms.+(?P<max>\d+)ms.+(?P<avg>\d+)ms")

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PING_COUNT, default=DEFAULT_PING_COUNT): vol.Range(
            min=1, max=100
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up the Ping Binary sensor."""
    setup_reload_service(hass, DOMAIN, PLATFORMS)

    host = config[CONF_HOST]
    count = config[CONF_PING_COUNT]
    name = config.get(CONF_NAME, f"{DEFAULT_NAME} {host}")

    try:
        # Verify we can create a raw socket, or
        # fallback to using a subprocess
        icmp_ping("127.0.0.1", count=0, timeout=0)
        ping_cls = PingDataICMPLib
    except SocketPermissionError:
        ping_cls = PingDataSubProcess

    ping_data = ping_cls(hass, host, count)

    add_entities([PingBinarySensor(name, ping_data)], True)


class PingBinarySensor(BinarySensorEntity):
    """Representation of a Ping Binary sensor."""

    def __init__(self, name: str, ping) -> None:
        """Initialize the Ping Binary sensor."""
        self._name = name
        self._ping = ping

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._ping.available

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the ICMP checo request."""
        if self._ping.data is not False:
            return {
                ATTR_ROUND_TRIP_TIME_AVG: self._ping.data["avg"],
                ATTR_ROUND_TRIP_TIME_MAX: self._ping.data["max"],
                ATTR_ROUND_TRIP_TIME_MDEV: self._ping.data["mdev"],
                ATTR_ROUND_TRIP_TIME_MIN: self._ping.data["min"],
            }

    async def async_update(self) -> None:
        """Get the latest data."""
        await self._ping.async_update()


class PingData:
    """The base class for handling the data retrieval."""

    def __init__(self, hass, host, count) -> None:
        """Initialize the data object."""
        self.hass = hass
        self._ip_address = host
        self._count = count
        self.data = {}
        self.available = False


class PingDataICMPLib(PingData):
    """The Class for handling the data retrieval using icmplib."""

    async def async_update(self) -> None:
        """Retrieve the latest details from the host."""
        _LOGGER.debug("ping address: %s", self._ip_address)
        data = await self.hass.async_add_executor_job(
            partial(
                icmp_ping,
                self._ip_address,
                count=self._count,
                id=async_get_next_ping_id(self.hass),
            )
        )
        self.available = data.is_alive
        if not self.available:
            self.data = False
            return

        self.data = {
            "min": data.min_rtt,
            "max": data.max_rtt,
            "avg": data.avg_rtt,
            "mdev": "",
        }


class PingDataSubProcess(PingData):
    """The Class for handling the data retrieval using the ping binary."""

    def __init__(self, hass, host, count) -> None:
        """Initialize the data object."""
        super().__init__(hass, host, count)
        if sys.platform == "win32":
            self._ping_cmd = [
                "ping",
                "-n",
                str(self._count),
                "-w",
                "1000",
                self._ip_address,
            ]
        else:
            self._ping_cmd = [
                "ping",
                "-n",
                "-q",
                "-c",
                str(self._count),
                "-W1",
                self._ip_address,
            ]

    async def async_ping(self):
        """Send ICMP echo request and return details if success."""
        pinger = await asyncio.create_subprocess_exec(
            *self._ping_cmd,
            stdin=None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out_data, out_error = await asyncio.wait_for(
                pinger.communicate(), self._count + PING_TIMEOUT
            )

            if out_data:
                _LOGGER.debug(
                    "Output of command: `%s`, return code: %s:\n%s",
                    " ".join(self._ping_cmd),
                    pinger.returncode,
                    out_data,
                )
            if out_error:
                _LOGGER.debug(
                    "Error of command: `%s`, return code: %s:\n%s",
                    " ".join(self._ping_cmd),
                    pinger.returncode,
                    out_error,
                )

            if pinger.returncode != 0:
                _LOGGER.exception(
                    "Error running command: `%s`, return code: %s",
                    " ".join(self._ping_cmd),
                    pinger.returncode,
                )

            if sys.platform == "win32":
                match = WIN32_PING_MATCHER.search(str(out_data).split("\n")[-1])
                rtt_min, rtt_avg, rtt_max = match.groups()
                return {"min": rtt_min, "avg": rtt_avg, "max": rtt_max, "mdev": ""}
            if "max/" not in str(out_data):
                match = PING_MATCHER_BUSYBOX.search(str(out_data).split("\n")[-1])
                rtt_min, rtt_avg, rtt_max = match.groups()
                return {"min": rtt_min, "avg": rtt_avg, "max": rtt_max, "mdev": ""}
            match = PING_MATCHER.search(str(out_data).split("\n")[-1])
            rtt_min, rtt_avg, rtt_max, rtt_mdev = match.groups()
            return {"min": rtt_min, "avg": rtt_avg, "max": rtt_max, "mdev": rtt_mdev}
        except asyncio.TimeoutError:
            _LOGGER.exception(
                "Timed out running command: `%s`, after: %ss",
                self._ping_cmd,
                self._count + PING_TIMEOUT,
            )
            if pinger:
                try:
                    await pinger.kill()
                except TypeError:
                    pass
                del pinger

            return False
        except AttributeError:
            return False

    async def async_update(self) -> None:
        """Retrieve the latest details from the host."""
        self.data = await self.async_ping()
        self.available = bool(self.data)
