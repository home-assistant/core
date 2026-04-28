"""DataUpdateCoordinator for the Thomson integration."""

from __future__ import annotations

from datetime import timedelta
import logging
import re
import telnetlib  # pylint: disable=deprecated-module
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

_DEVICES_REGEX = re.compile(
    r"(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2})))\s"
    r"(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s+"
    r"(?P<status>([^\s]+))\s+"
    r"(?P<type>([^\s]+))\s+"
    r"(?P<intf>([^\s]+))\s+"
    r"(?P<hwintf>([^\s]+))\s+"
    r"(?P<host>([^\s]+))"
)

type ThomsonConfigEntry = ConfigEntry[ThomsonDataUpdateCoordinator]


class ThomsonDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, dict[str, str]]]
):
    """Coordinator for Thomson router device tracking."""

    config_entry: ThomsonConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ThomsonConfigEntry) -> None:
        """Initialize the coordinator."""
        self._host: str = config_entry.data[CONF_HOST]
        self._username: str = config_entry.data[CONF_USERNAME]
        self._password: str = config_entry.data[CONF_PASSWORD]
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self._host}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, dict[str, str]]:
        """Fetch data from the Thomson router."""
        data = await self.hass.async_add_executor_job(self._fetch_devices)
        if data is None:
            raise UpdateFailed(f"Error communicating with Thomson router {self._host}")
        return data

    def _fetch_devices(self) -> dict[str, dict[str, str]] | None:
        """Retrieve connected devices from the Thomson router via telnet."""
        try:
            telnet = telnetlib.Telnet(self._host)
            telnet.read_until(b"Username : ")
            telnet.write((self._username + "\r\n").encode("ascii"))
            telnet.read_until(b"Password : ")
            telnet.write((self._password + "\r\n").encode("ascii"))
            telnet.read_until(b"=>")
            telnet.write(b"hostmgr list\r\n")
            devices_result = telnet.read_until(b"=>").split(b"\r\n")
            telnet.write(b"exit\r\n")
        except EOFError:
            _LOGGER.exception("Unexpected response from Thomson router")
            return None
        except ConnectionRefusedError:
            _LOGGER.exception(
                "Connection refused by Thomson router. Is telnet enabled?"
            )
            return None

        devices: dict[str, dict[str, str]] = {}
        for device in devices_result:
            if match := _DEVICES_REGEX.search(device.decode("utf-8")):
                mac = match.group("mac").upper()
                if "C" in match.group("status"):
                    devices[mac] = {
                        "mac": mac,
                        "ip": match.group("ip"),
                        "host": match.group("host"),
                    }
        return devices


def validate_connection(data: dict[str, Any]) -> None:
    """Validate that we can connect to the Thomson router.

    Raises ConnectionRefusedError or EOFError on failure.
    """
    telnet = telnetlib.Telnet(data[CONF_HOST])
    telnet.read_until(b"Username : ")
    telnet.write((data[CONF_USERNAME] + "\r\n").encode("ascii"))
    telnet.read_until(b"Password : ")
    telnet.write((data[CONF_PASSWORD] + "\r\n").encode("ascii"))
    telnet.read_until(b"=>")
    telnet.write(b"exit\r\n")
