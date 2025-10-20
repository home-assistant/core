"""Support for EnOcean roller shutters."""

from __future__ import annotations

import asyncio
from enum import Enum
import logging
from typing import Any

from enocean.protocol.constants import RORG
from enocean.protocol.packet import Packet, RadioPacket
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .config_flow import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_NAME,
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    CONF_ENOCEAN_DEVICES,
    CONF_ENOCEAN_SENDER_ID,
)
from .const import SIGNAL_SEND_MESSAGE
from .enocean_id import EnOceanID
from .entity import EnOceanEntity
from .supported_device_type import (
    EnOceanSupportedDeviceType,
    get_supported_enocean_device_types,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "EnOcean roller shutter"

CONF_SENDER_ID = "sender_id"

WATCHDOG_TIMEOUT = 1
WATCHDOG_INTERVAL = 0.2
WATCHDOG_MAX_QUERIES = 10

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    devices = config_entry.options.get(CONF_ENOCEAN_DEVICES, [])

    for device in devices:
        device_type_id = device[CONF_ENOCEAN_DEVICE_TYPE_ID]
        device_type = get_supported_enocean_device_types()[device_type_id]
        eep = device_type.eep
        if eep != "D2-05-00":
            continue

        device_id = EnOceanID(device[CONF_ENOCEAN_DEVICE_ID])
        sender_id = EnOceanID(0)
        if device[CONF_ENOCEAN_SENDER_ID] != "":
            sender_id = EnOceanID(device[CONF_ENOCEAN_SENDER_ID])

        async_add_entities(
            [
                EnOceanCover(
                    sender_id=sender_id,
                    enocean_device_id=device_id,
                    gateway_id=config_entry.runtime_data.gateway.chip_id,
                    device_name=device[CONF_ENOCEAN_DEVICE_NAME],
                    dev_type=device_type,
                    name=None,
                )
            ]
        )


class EnOceanCoverCommand(Enum):
    """The possible commands to be sent to an EnOcean cover."""

    SET_POSITION = 1
    STOP = 2
    QUERY_POSITION = 3


class EnOceanCover(EnOceanEntity, CoverEntity):
    """Representation of an EnOcean Cover (EEP D2-05-00)."""

    def __init__(
        self,
        sender_id: EnOceanID,
        enocean_device_id: EnOceanID,
        gateway_id: EnOceanID,
        device_name: str,
        dev_type: EnOceanSupportedDeviceType,
        name: str | None,
    ) -> None:
        """Initialize the EnOcean Cover."""
        super().__init__(
            enocean_id=enocean_device_id,
            gateway_id=gateway_id,
            device_name=device_name,
            dev_type=dev_type,
            name=name,
        )
        self._attr_device_class = CoverDeviceClass.BLIND
        self._position: int | None = None
        self._attr_is_closed: bool | None = None
        self._is_opening = False
        self._is_closing = False
        self._sender_id: EnOceanID = sender_id
        self._state_changed_by_command = False
        self._stop_suspected = False
        self._watchdog_enabled = False
        self._watchdog_seconds_remaining: float = 0
        self._watchdog_queries_remaining: int = 5
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover position."""
        return self._position

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        return self._is_opening

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        return self._is_closing

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._attr_is_closed

    async def async_added_to_hass(self) -> None:
        """Query status after Home Assistant (re)start."""
        await super().async_added_to_hass()
        self.start_or_feed_watchdog()

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._state_changed_by_command = True
        self._is_opening = True
        self._is_closing = False
        self.start_or_feed_watchdog()
        self.send_telegram(EnOceanCoverCommand.SET_POSITION, 0)

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._state_changed_by_command = True
        self._is_opening = False
        self._is_closing = True
        self.start_or_feed_watchdog()
        self.send_telegram(EnOceanCoverCommand.SET_POSITION, 100)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        self._state_changed_by_command = True

        if kwargs[ATTR_POSITION] == self._position:
            self._is_opening = False
            self._is_closing = False
        elif kwargs[ATTR_POSITION] > self._position:
            self._is_opening = True
            self._is_closing = False
        elif kwargs[ATTR_POSITION] < self._position:
            self._is_opening = False
            self._is_closing = True

        self.start_or_feed_watchdog()
        self.send_telegram(
            EnOceanCoverCommand.SET_POSITION, 100 - kwargs[ATTR_POSITION]
        )

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop any cover movement."""
        self.stop_watchdog()
        self._state_changed_by_command = True
        self._is_opening = False
        self._is_closing = False
        self.send_telegram(EnOceanCoverCommand.STOP)

    def value_changed(self, packet: Packet) -> None:
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.
        """
        # position is inversed in Home Assistant and in EnOcean:
        # 0 means 'closed' in Home Assistant and 'open' in EnOcean
        # 100 means 'open' in Home Assistant and 'closed' in EnOcean

        new_position = 100 - packet.data[1]

        if self._position is not None:
            if self._state_changed_by_command:
                self._state_changed_by_command = False

            elif new_position in (0, 100):
                self._is_opening = False
                self._is_closing = False
                self.stop_watchdog()

            elif new_position == self._position:
                if self._stop_suspected:
                    self._stop_suspected = False
                    self._is_opening = False
                    self._is_closing = False
                    self.stop_watchdog()
                else:
                    self.start_or_feed_watchdog()
                    self._stop_suspected = True
                    return

            elif new_position > self._position:
                self._is_opening = True
                self._is_closing = False
                self.start_or_feed_watchdog()

            elif new_position < self._position:
                self._is_opening = False
                self._is_closing = True
                self.start_or_feed_watchdog()

        self._position = new_position
        if self._position == 0:
            self._attr_is_closed = True
        else:
            self._attr_is_closed = False

        self.schedule_update_ha_state()

    def send_telegram(self, command: EnOceanCoverCommand, position: int = 0) -> None:
        """Send an EnOcean telegram with the respective command."""
        _LOGGER.warning(self.enocean_device_id.to_bytelist())
        packet = RadioPacket.create(
            rorg=RORG.VLD,
            rorg_func=0x05,
            rorg_type=0x00,
            destination=self.enocean_device_id.to_bytelist(),
            sender=self._sender_id.to_bytelist(),
            command=command.value,
            POS=position,
        )
        dispatcher_send(self.hass, SIGNAL_SEND_MESSAGE, packet)

    def start_or_feed_watchdog(self) -> None:
        """Start or feed the 'movement stop' watchdog."""
        self._watchdog_seconds_remaining = WATCHDOG_TIMEOUT
        self._watchdog_queries_remaining = WATCHDOG_MAX_QUERIES

        if self._watchdog_enabled:
            return

        self._watchdog_enabled = True
        self.hass.create_task(self.watchdog())

    def stop_watchdog(self) -> None:
        """Stop the 'movement stop' watchdog."""
        self._watchdog_enabled = False

    async def watchdog(self) -> None:
        """Watchdog to check if the cover movement stopped.

        After watchdog time expired, the watchdog queries the current status.
        """

        while 1:
            await asyncio.sleep(WATCHDOG_INTERVAL)

            if not self._watchdog_enabled:
                return

            if self._watchdog_seconds_remaining <= 0:
                self.send_telegram(EnOceanCoverCommand.QUERY_POSITION)
                self._watchdog_seconds_remaining = WATCHDOG_TIMEOUT
                self._watchdog_queries_remaining -= 1

                if self._watchdog_queries_remaining == 0:
                    _LOGGER.debug(
                        "'Movement stop' watchdog max query limit reached. Disabling watchdog and setting state to 'unknown'"
                    )
                    self._position = None
                    self._attr_is_closed = None
                    self._is_opening = False
                    self._is_closing = False
                    return
                continue

            self._watchdog_seconds_remaining -= WATCHDOG_INTERVAL
