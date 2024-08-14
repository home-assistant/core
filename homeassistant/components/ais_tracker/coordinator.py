"""AIS tracker coordinator."""

from __future__ import annotations

import asyncio
import logging
from socket import AF_INET, SO_REUSEPORT, SOCK_DGRAM, SOL_SOCKET, socket

from pyais.stream import SocketStream

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.json import json_loads_object

from .const import CONF_MMSIS, DOMAIN

LOGGER = logging.getLogger(__name__)

type AisTrackerConfigEntry = ConfigEntry[AisTrackerCoordinator]


class UDPReceiver(SocketStream):
    """Re-implementation of pyais.stream.UDPReceiver.

    can be removed, as soon as https://github.com/M0r13n/pyais/pull/148 is merged.
    """

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


class AisTrackerCoordinator(
    DataUpdateCoordinator[dict[str, dict[str, float | int | str | None]]]
):
    """AIS tracker data update coordinator."""

    config_entry: AisTrackerConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the AIS tracker coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self._receiver: UDPReceiver | None = None
        self._background_task: asyncio.Task | None = None
        self.data = {}

    async def async_setup(self) -> None:
        """Set up the AIS tracker coordinator."""

        self._receiver = UDPReceiver("", self.config_entry.data[CONF_PORT])

        async def async_ais_listerner():
            def ais_listerner():
                for msg_raw in self._receiver:
                    msg = json_loads_object(msg_raw.decode().to_json())
                    LOGGER.debug("received msg: %s", msg)
                    if (
                        msg.get("msg_type") in [1, 2, 3, 5]
                        and str(msg.get("mmsi")) in self.config_entry.data[CONF_MMSIS]
                    ):
                        self.hass.create_task(self.async_process_ais_message(msg))

            await self.hass.async_add_executor_job(ais_listerner)

        self._background_task = self.config_entry.async_create_background_task(
            hass=self.hass,
            target=async_ais_listerner(),
            name=f"{DOMAIN}_ais_listerner",
            eager_start=False,
        )

        self.config_entry.async_on_unload(self.async_teardown)

    async def async_teardown(self) -> None:
        """Tear down the AIS tracker coordinator."""
        if self._receiver is not None:
            self._receiver.close()
        if self._background_task is not None:
            self._background_task.cancel()

    async def async_process_ais_message(self, message: dict) -> None:
        """Process incoming ais message."""
        LOGGER.debug("process ais message: %s", message)
        if message.get("msg_type") in [1, 2, 3]:  # position reports
            data = {**self.data}
            data[str(message["mmsi"])] = message
            self.async_set_updated_data(data)

        elif message.get("msg_type") == 5:  # Static and voyage related data
            dreg = dr.async_get(self.hass)
            dreg.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, str(message["mmsi"]))},
                name=f"{message.get('shipname')} ({message.get('callsign')})",
                serial_number=str(message["mmsi"]),
                manufacturer="AIS tracker",
            )
