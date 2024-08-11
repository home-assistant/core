"""AIS tracker."""

from asyncio import Task
from dataclasses import dataclass
import logging
from socket import AF_INET, SO_REUSEPORT, SOCK_DGRAM, SOL_SOCKET, socket

from pyais.stream import SocketStream

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.json import json_loads_object

from .const import CONF_MMSIS, DOMAIN

LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


class UDPReceiver(SocketStream):
    """Re-implementation of pyais.stream.UDPReceiver."""

    _fobj: socket

    def __init__(self, host: str, port: int) -> None:
        """Initialize the UDP receiver."""
        sock: socket = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEPORT, 1)
        sock.bind((host, port))
        super().__init__(sock, preprocessor=None)

    def recv(self) -> bytes:
        """Receive data from socket."""
        return self._fobj.recvfrom(self.BUF_SIZE)[0]

    def close(self) -> None:
        """Close the UDP receiver."""
        self._fobj.close()


@dataclass
class AisTrackerData:
    """Runtime data."""

    receiver: UDPReceiver
    background_task: Task


type AisTrackerConfigEntry = ConfigEntry[AisTrackerData]


async def async_setup_entry(hass: HomeAssistant, entry: AisTrackerConfigEntry) -> bool:
    """Set up config entry."""

    receiver = UDPReceiver("", entry.data[CONF_PORT])

    async def async_ais_listerner():
        def ais_listerner():
            for msg_raw in receiver:
                msg = json_loads_object(msg_raw.decode().to_json())
                LOGGER.debug("received msg: %s", msg)
                if (
                    msg.get("msg_type") in [1, 2, 3, 5]
                    and (mmsi := str(msg.get("mmsi"))) in entry.data[CONF_MMSIS]
                ):
                    hass.bus.fire(f"{DOMAIN}_{mmsi}", msg)

        await hass.async_add_executor_job(ais_listerner)

    task = entry.async_create_background_task(
        hass=hass,
        target=async_ais_listerner(),
        name=f"{DOMAIN}_ais_listerner",
        eager_start=False,
    )

    entry.runtime_data = AisTrackerData(receiver, task)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AisTrackerConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.receiver.close()
    entry.runtime_data.background_task.cancel()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
