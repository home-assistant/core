"""Data update coordinator for the Actiontec integration."""

from datetime import timedelta
import logging
from typing import override

import telnetlib  # pylint: disable=deprecated-module

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LEASES_REGEX
from .model import Device

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type ActiontecConfigEntry = ConfigEntry[ActiontecDataUpdateCoordinator]


def get_actiontec_data(host: str, username: str, password: str) -> list[Device] | None:
    """Retrieve data from Actiontec MI424WR and return parsed result."""
    try:
        telnet = telnetlib.Telnet(host)
        telnet.read_until(b"Username: ")
        telnet.write((f"{username}\n").encode("ascii"))
        telnet.read_until(b"Password: ")
        telnet.write((f"{password}\n").encode("ascii"))
        prompt = telnet.read_until(b"Wireless Broadband Router> ").split(b"\n")[-1]
        telnet.write(b"firewall mac_cache_dump\n")
        telnet.write(b"\n")
        telnet.read_until(prompt)
        leases_result = telnet.read_until(prompt).split(b"\n")[1:-1]
        telnet.write(b"exit\n")
    except EOFError:
        _LOGGER.exception("Unexpected response from router")
        return None
    except OSError:
        _LOGGER.exception("Could not connect to router. Telnet enabled?")
        return None

    devices: list[Device] = []
    for lease in leases_result:
        match = LEASES_REGEX.search(lease.decode("utf-8"))
        if match is not None:
            devices.append(
                Device(
                    match.group("ip"),
                    match.group("mac").upper(),
                    int(match.group("timevalid")),
                )
            )
    return devices


class ActiontecDataUpdateCoordinator(DataUpdateCoordinator[list[Device]]):
    """Class to manage fetching data from the Actiontec router."""

    config_entry: ActiontecConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ActiontecConfigEntry) -> None:
        """Initialize the coordinator using the config entry."""
        self.host = config_entry.data[CONF_HOST]
        self.username = config_entry.data[CONF_USERNAME]
        self.password = config_entry.data[CONF_PASSWORD]
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> list[Device]:
        """Fetch connected devices from the Actiontec router."""
        if (
            devices := await self.hass.async_add_executor_job(
                get_actiontec_data, self.host, self.username, self.password
            )
        ) is None:
            raise UpdateFailed(
                f"Failed to fetch data from Actiontec router {self.host}"
            )
        return [device for device in devices if device.timevalid > -60]
