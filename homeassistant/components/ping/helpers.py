"""Ping classes shared between platforms."""

import asyncio
from contextlib import suppress
import logging
import re
from typing import TYPE_CHECKING, Any

from icmplib import NameLookupError, async_ping

from homeassistant.core import HomeAssistant

from .const import ICMP_TIMEOUT, PING_TIMEOUT

_LOGGER = logging.getLogger(__name__)

PING_MATCHER = re.compile(
    r"(?P<min>\d+.\d+)\/(?P<avg>\d+.\d+)\/(?P<max>\d+.\d+)\/(?P<mdev>\d+.\d+)"
)

PING_MATCHER_BUSYBOX = re.compile(
    r"(?P<min>\d+.\d+)\/(?P<avg>\d+.\d+)\/(?P<max>\d+.\d+)"
)

WIN32_PING_MATCHER = re.compile(r"(?P<min>\d+)ms.+(?P<max>\d+)ms.+(?P<avg>\d+)ms")


class PingData:
    """The base class for handling the data retrieval."""

    data: dict[str, Any] | None = None
    is_alive: bool = False

    def __init__(self, hass: HomeAssistant, host: str, count: int) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.ip_address = host
        self._count = count


class PingDataICMPLib(PingData):
    """The Class for handling the data retrieval using icmplib."""

    def __init__(
        self, hass: HomeAssistant, host: str, count: int, privileged: bool | None
    ) -> None:
        """Initialize the data object."""
        super().__init__(hass, host, count)
        self._privileged = privileged

    async def async_update(self) -> None:
        """Retrieve the latest details from the host."""
        _LOGGER.debug("ping address: %s", self.ip_address)
        try:
            data = await async_ping(
                self.ip_address,
                count=self._count,
                timeout=ICMP_TIMEOUT,
                privileged=self._privileged,
            )
        except NameLookupError:
            _LOGGER.debug("Error resolving host: %s", self.ip_address)
            self.is_alive = False
            return

        _LOGGER.debug(
            "async_ping returned: reachable=%s sent=%i received=%s",
            data.is_alive,
            data.packets_sent,
            data.packets_received,
        )

        self.is_alive = data.is_alive
        if not self.is_alive:
            self.data = None
            return

        self.data = {
            "min": data.min_rtt,
            "max": data.max_rtt,
            "avg": data.avg_rtt,
        }


class PingDataSubProcess(PingData):
    """The Class for handling the data retrieval using the ping binary."""

    def __init__(
        self, hass: HomeAssistant, host: str, count: int, privileged: bool | None
    ) -> None:
        """Initialize the data object."""
        super().__init__(hass, host, count)
        self._ping_cmd = [
            "ping",
            "-n",
            "-q",
            "-c",
            str(self._count),
            "-W1",
            self.ip_address,
        ]

    async def async_ping(self) -> dict[str, Any] | None:
        """Send ICMP echo request and return details if success."""
        _LOGGER.debug(
            "Pinging %s with: `%s`", self.ip_address, " ".join(self._ping_cmd)
        )

        pinger = await asyncio.create_subprocess_exec(
            *self._ping_cmd,
            stdin=None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            close_fds=False,  # required for posix_spawn
        )
        try:
            async with asyncio.timeout(self._count + PING_TIMEOUT):
                out_data, out_error = await pinger.communicate()

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

            if pinger.returncode and pinger.returncode > 1:
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
                if TYPE_CHECKING:
                    assert match is not None
                rtt_min, rtt_avg, rtt_max = match.groups()
                return {"min": rtt_min, "avg": rtt_avg, "max": rtt_max}
            match = PING_MATCHER.search(str(out_data).rsplit("\n", maxsplit=1)[-1])
            if TYPE_CHECKING:
                assert match is not None
            rtt_min, rtt_avg, rtt_max, rtt_mdev = match.groups()
        except TimeoutError:
            _LOGGER.debug(
                "Timed out running command: `%s`, after: %s",
                " ".join(self._ping_cmd),
                self._count + PING_TIMEOUT,
            )

            if pinger:
                with suppress(TypeError):
                    await pinger.kill()  # type: ignore[func-returns-value]
                del pinger

            return None
        except AttributeError as err:
            _LOGGER.debug("Error matching ping output: %s", err)
            return None
        return {"min": rtt_min, "avg": rtt_avg, "max": rtt_max, "mdev": rtt_mdev}

    async def async_update(self) -> None:
        """Retrieve the latest details from the host."""
        self.data = await self.async_ping()
        self.is_alive = self.data is not None
