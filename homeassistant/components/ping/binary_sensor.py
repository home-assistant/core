"""Tracks the latency of a host by sending ICMP echo requests (ping)."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
import logging
import re
from typing import Any

from icmplib import NameLookupError, async_ping
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, ICMP_TIMEOUT, PING_PRIVS, PING_TIMEOUT

_LOGGER = logging.getLogger(__name__)


ATTR_ROUND_TRIP_TIME_AVG = "round_trip_time_avg"
ATTR_ROUND_TRIP_TIME_MAX = "round_trip_time_max"
ATTR_ROUND_TRIP_TIME_MDEV = "round_trip_time_mdev"
ATTR_ROUND_TRIP_TIME_MIN = "round_trip_time_min"

CONF_PING_COUNT = "count"

DEFAULT_NAME = "Ping"
DEFAULT_PING_COUNT = 5

SCAN_INTERVAL = timedelta(minutes=5)

PARALLEL_UPDATES = 50

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ping Binary sensor."""
    host = config[CONF_HOST]
    count = config[CONF_PING_COUNT]
    name = config.get(CONF_NAME, f"{DEFAULT_NAME} {host}")
    privileged = hass.data[DOMAIN][PING_PRIVS]
    ping_cls: type[PingDataSubProcess | PingDataICMPLib]
    if privileged is None:
        ping_cls = PingDataSubProcess
    else:
        ping_cls = PingDataICMPLib

    async_add_entities(
        [PingBinarySensor(name, ping_cls(hass, host, count, privileged))]
    )


class PingBinarySensor(RestoreEntity, BinarySensorEntity):
    """Representation of a Ping Binary sensor."""

    def __init__(self, name: str, ping: PingDataSubProcess | PingDataICMPLib) -> None:
        """Initialize the Ping Binary sensor."""
        self._available = False
        self._name = name
        self._ping = ping

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def available(self) -> bool:
        """Return if we have done the first ping."""
        return self._available

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this sensor."""
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._ping.is_alive

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the ICMP checo request."""
        if self._ping.data is None:
            return None
        return {
            ATTR_ROUND_TRIP_TIME_AVG: self._ping.data["avg"],
            ATTR_ROUND_TRIP_TIME_MAX: self._ping.data["max"],
            ATTR_ROUND_TRIP_TIME_MDEV: self._ping.data["mdev"],
            ATTR_ROUND_TRIP_TIME_MIN: self._ping.data["min"],
        }

    async def async_update(self) -> None:
        """Get the latest data."""
        await self._ping.async_update()
        self._available = True

    async def async_added_to_hass(self):
        """Restore previous state on restart to avoid blocking startup."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._available = True

        if last_state is None or last_state.state != STATE_ON:
            self._ping.data = None
            return

        attributes = last_state.attributes
        self._ping.is_alive = True
        self._ping.data = {
            "min": attributes[ATTR_ROUND_TRIP_TIME_MIN],
            "max": attributes[ATTR_ROUND_TRIP_TIME_MAX],
            "avg": attributes[ATTR_ROUND_TRIP_TIME_AVG],
            "mdev": attributes[ATTR_ROUND_TRIP_TIME_MDEV],
        }


class PingData:
    """The base class for handling the data retrieval."""

    def __init__(self, hass, host, count) -> None:
        """Initialize the data object."""
        self.hass = hass
        self._ip_address = host
        self._count = count
        self.data: dict[str, Any] | None = None
        self.is_alive = False


class PingDataICMPLib(PingData):
    """The Class for handling the data retrieval using icmplib."""

    def __init__(self, hass, host, count, privileged) -> None:
        """Initialize the data object."""
        super().__init__(hass, host, count)
        self._privileged = privileged

    async def async_update(self) -> None:
        """Retrieve the latest details from the host."""
        _LOGGER.debug("ping address: %s", self._ip_address)
        try:
            data = await async_ping(
                self._ip_address,
                count=self._count,
                timeout=ICMP_TIMEOUT,
                privileged=self._privileged,
            )
        except NameLookupError:
            self.is_alive = False
            return

        self.is_alive = data.is_alive
        if not self.is_alive:
            self.data = None
            return

        self.data = {
            "min": data.min_rtt,
            "max": data.max_rtt,
            "avg": data.avg_rtt,
            "mdev": "",
        }


class PingDataSubProcess(PingData):
    """The Class for handling the data retrieval using the ping binary."""

    def __init__(self, hass, host, count, privileged) -> None:
        """Initialize the data object."""
        super().__init__(hass, host, count)
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

            if pinger.returncode > 1:
                # returncode of 1 means the host is unreachable
                _LOGGER.exception(
                    "Error running command: `%s`, return code: %s",
                    " ".join(self._ping_cmd),
                    pinger.returncode,
                )

            if "max/" not in str(out_data):
                match = PING_MATCHER_BUSYBOX.search(
                    str(out_data).rsplit("\n", maxsplit=1)[-1]
                )
                rtt_min, rtt_avg, rtt_max = match.groups()
                return {"min": rtt_min, "avg": rtt_avg, "max": rtt_max, "mdev": ""}
            match = PING_MATCHER.search(str(out_data).rsplit("\n", maxsplit=1)[-1])
            rtt_min, rtt_avg, rtt_max, rtt_mdev = match.groups()
            return {"min": rtt_min, "avg": rtt_avg, "max": rtt_max, "mdev": rtt_mdev}
        except asyncio.TimeoutError:
            _LOGGER.exception(
                "Timed out running command: `%s`, after: %ss",
                self._ping_cmd,
                self._count + PING_TIMEOUT,
            )
            if pinger:
                with suppress(TypeError):
                    await pinger.kill()
                del pinger

            return None
        except AttributeError:
            return None

    async def async_update(self) -> None:
        """Retrieve the latest details from the host."""
        self.data = await self.async_ping()
        self.is_alive = self.data is not None
