"""Support for the DIRECTV remote."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
import logging
from typing import Any

from directv import DIRECTV, DIRECTVError

from homeassistant.components.remote import ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DIRECTVEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=2)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Load DirecTV remote based on a config entry."""
    dtv = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for location in dtv.device.locations:
        entities.append(
            DIRECTVRemote(
                dtv=dtv,
                name=str.title(location.name),
                address=location.address,
            )
        )

    async_add_entities(entities, True)


class DIRECTVRemote(DIRECTVEntity, RemoteEntity):
    """Device that sends commands to a DirecTV receiver."""

    def __init__(self, *, dtv: DIRECTV, name: str, address: str = "0") -> None:
        """Initialize DirecTV remote."""
        super().__init__(
            dtv=dtv,
            name=name,
            address=address,
        )

        self._available = False
        self._is_on = True

    @property
    def available(self):
        """Return if able to retrieve information from device or not."""
        return self._available

    @property
    def unique_id(self):
        """Return a unique ID."""
        if self._address == "0":
            return self.dtv.device.info.receiver_id

        return self._address

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    async def async_update(self) -> None:
        """Update device state."""
        status = await self.dtv.status(self._address)

        if status in ("active", "standby"):
            self._available = True
            self._is_on = status == "active"
        else:
            self._available = False
            self._is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.dtv.remote("poweron", self._address)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.dtv.remote("poweroff", self._address)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to a device.

        Supported keys: power, poweron, poweroff, format,
        pause, rew, replay, stop, advance, ffwd, record,
        play, guide, active, list, exit, back, menu, info,
        up, down, left, right, select, red, green, yellow,
        blue, chanup, chandown, prev, 0, 1, 2, 3, 4, 5,
        6, 7, 8, 9, dash, enter
        """
        num_repeats = kwargs[ATTR_NUM_REPEATS]

        for _ in range(num_repeats):
            for single_command in command:
                try:
                    await self.dtv.remote(single_command, self._address)
                except DIRECTVError:
                    _LOGGER.exception(
                        "Sending command %s to device %s failed",
                        single_command,
                        self._device_id,
                    )
