"""Sensor to monitor incoming/outgoing phone calls on a Fritz!Box router."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
import logging
import queue
from threading import Event as ThreadingEvent, Thread
from time import sleep
from typing import Any, cast

from fritzconnection.core.fritzmonitor import FritzMonitor

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import FritzBoxPhonebook
from .const import (
    ATTR_PREFIXES,
    CONF_PHONEBOOK,
    CONF_PREFIXES,
    DOMAIN,
    FRITZBOX_PHONEBOOK,
    MANUFACTURER,
    SERIAL_NUMBER,
    FritzState,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=3)


class CallState(StrEnum):
    """Fritz sensor call states."""

    RINGING = "ringing"
    DIALING = "dialing"
    TALKING = "talking"
    IDLE = "idle"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fritzbox_callmonitor sensor from config_entry."""
    fritzbox_phonebook: FritzBoxPhonebook = hass.data[DOMAIN][config_entry.entry_id][
        FRITZBOX_PHONEBOOK
    ]

    phonebook_id: int = config_entry.data[CONF_PHONEBOOK]
    prefixes: list[str] | None = config_entry.options.get(CONF_PREFIXES)
    serial_number: str = config_entry.data[SERIAL_NUMBER]
    host: str = config_entry.data[CONF_HOST]
    port: int = config_entry.data[CONF_PORT]

    unique_id = f"{serial_number}-{phonebook_id}"

    sensor = FritzBoxCallSensor(
        phonebook_name=config_entry.title,
        unique_id=unique_id,
        fritzbox_phonebook=fritzbox_phonebook,
        prefixes=prefixes,
        host=host,
        port=port,
    )

    async_add_entities([sensor])


class FritzBoxCallSensor(SensorEntity):
    """Implementation of a Fritz!Box call monitor."""

    _attr_has_entity_name = True
    _attr_translation_key = DOMAIN
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(CallState)

    def __init__(
        self,
        phonebook_name: str,
        unique_id: str,
        fritzbox_phonebook: FritzBoxPhonebook,
        prefixes: list[str] | None,
        host: str,
        port: int,
    ) -> None:
        """Initialize the sensor."""
        self._fritzbox_phonebook = fritzbox_phonebook
        self._prefixes = prefixes
        self._host = host
        self._port = port
        self._monitor: FritzBoxCallMonitor | None = None
        self._attributes: dict[str, str | list[str]] = {}

        self._attr_translation_placeholders = {"phonebook_name": phonebook_name}
        self._attr_unique_id = unique_id
        self._attr_native_value = CallState.IDLE
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            model=self._fritzbox_phonebook.fph.modelname,
            name=self._fritzbox_phonebook.fph.modelname,
            sw_version=self._fritzbox_phonebook.fph.fc.system_version,
        )

    async def async_added_to_hass(self) -> None:
        """Connect to FRITZ!Box to monitor its call state."""
        await super().async_added_to_hass()
        await self.hass.async_add_executor_job(self._start_call_monitor)
        self.async_on_remove(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._stop_call_monitor
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from FRITZ!Box by stopping monitor."""
        await super().async_will_remove_from_hass()
        await self.hass.async_add_executor_job(self._stop_call_monitor)

    def _start_call_monitor(self) -> None:
        """Check connection and start callmonitor thread."""
        _LOGGER.debug("Starting monitor for: %s", self.entity_id)
        self._monitor = FritzBoxCallMonitor(
            host=self._host,
            port=self._port,
            sensor=self,
        )
        self._monitor.connect()

    def _stop_call_monitor(self, event: Event | None = None) -> None:
        """Stop callmonitor thread."""
        if (
            self._monitor
            and self._monitor.stopped
            and not self._monitor.stopped.is_set()
            and self._monitor.connection
            and self._monitor.connection.is_alive
        ):
            self._monitor.stopped.set()
            self._monitor.connection.stop()
            _LOGGER.debug("Stopped monitor for: %s", self.entity_id)

    def set_state(self, state: CallState) -> None:
        """Set the state."""
        self._attr_native_value = state

    def set_attributes(self, attributes: Mapping[str, str]) -> None:
        """Set the state attributes."""
        self._attributes = {**attributes}

    @property
    def extra_state_attributes(self) -> dict[str, str | list[str]]:
        """Return the state attributes."""
        if self._prefixes:
            self._attributes[ATTR_PREFIXES] = self._prefixes
        return self._attributes

    def number_to_name(self, number: str) -> str:
        """Return a name for a given phone number."""
        return self._fritzbox_phonebook.get_name(number)

    def update(self) -> None:
        """Update the phonebook if it is defined."""
        self._fritzbox_phonebook.update_phonebook()


class FritzBoxCallMonitor:
    """Event listener to monitor calls on the Fritz!Box."""

    def __init__(self, host: str, port: int, sensor: FritzBoxCallSensor) -> None:
        """Initialize Fritz!Box monitor instance."""
        self.host = host
        self.port = port
        self.connection: FritzMonitor | None = None
        self.stopped = ThreadingEvent()
        self._sensor = sensor

    def connect(self) -> None:
        """Connect to the Fritz!Box."""
        _LOGGER.debug("Setting up socket connection")
        try:
            self.connection = FritzMonitor(address=self.host, port=self.port)
            kwargs: dict[str, Any] = {
                "event_queue": self.connection.start(
                    reconnect_tries=50, reconnect_delay=120
                )
            }
            Thread(target=self._process_events, kwargs=kwargs).start()
        except OSError as err:
            self.connection = None
            _LOGGER.error(
                "Cannot connect to %s on port %s: %s", self.host, self.port, err
            )

    def _process_events(self, event_queue: queue.Queue[str]) -> None:
        """Listen to incoming or outgoing calls."""
        _LOGGER.debug("Connection established, waiting for events")
        while not self.stopped.is_set():
            try:
                event = event_queue.get(timeout=10)
            except queue.Empty:
                if (
                    not cast(FritzMonitor, self.connection).is_alive
                    and not self.stopped.is_set()
                ):
                    _LOGGER.error("Connection has abruptly ended")
                _LOGGER.debug("Empty event queue")
                continue
            else:
                _LOGGER.debug("Received event: %s", event)
                self._parse(event)
                sleep(1)

    def _parse(self, event: str) -> None:
        """Parse the call information and set the sensor states."""
        line = event.split(";")
        df_in = "%d.%m.%y %H:%M:%S"
        df_out = "%Y-%m-%dT%H:%M:%S"
        isotime = datetime.strptime(line[0], df_in).strftime(df_out)
        if line[1] == FritzState.RING:
            self._sensor.set_state(CallState.RINGING)
            att = {
                "type": "incoming",
                "from": line[3],
                "to": line[4],
                "device": line[5],
                "initiated": isotime,
                "from_name": self._sensor.number_to_name(line[3]),
            }
            self._sensor.set_attributes(att)
        elif line[1] == FritzState.CALL:
            self._sensor.set_state(CallState.DIALING)
            att = {
                "type": "outgoing",
                "from": line[4],
                "to": line[5],
                "device": line[6],
                "initiated": isotime,
                "to_name": self._sensor.number_to_name(line[5]),
            }
            self._sensor.set_attributes(att)
        elif line[1] == FritzState.CONNECT:
            self._sensor.set_state(CallState.TALKING)
            att = {
                "with": line[4],
                "device": line[3],
                "accepted": isotime,
                "with_name": self._sensor.number_to_name(line[4]),
            }
            self._sensor.set_attributes(att)
        elif line[1] == FritzState.DISCONNECT:
            self._sensor.set_state(CallState.IDLE)
            att = {"duration": line[3], "closed": isotime}
            self._sensor.set_attributes(att)
        self._sensor.schedule_update_ha_state()
