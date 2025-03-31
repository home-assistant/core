"""LEA Zone Structure."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)


class LeaZone:
    """LeaZone."""

    def __init__(self, controller, zone_id: str) -> None:
        """Init."""

        self._zone_id = zone_id
        self._controller = controller
        self._lastseen: datetime = datetime.now()

        self._zone_name: str = "Zone " + str(zone_id)
        self._model: str = ""
        self._power: bool = True
        self._volume: float = 0.5
        self._mute: bool = True
        self._source: str = ""
        self._update_callback: Callable[[LeaZone], None] | None = None
        self.is_manual: bool = False

    @property
    def update_callback(
        self,
    ) -> Callable[[LeaZone], None] | None:
        """Get Update Callback."""
        return self._update_callback

    def set_update_callback(
        self,
        callback: Callable[[LeaZone], None] | None,
    ) -> Callable[[LeaZone], None] | None:
        """Set Update Callback."""
        old_callback = self._update_callback
        self._update_callback = callback
        return old_callback

    @property
    def controller(self):
        """Controller."""
        return self._controller

    @property
    def zone_id(self) -> str:
        """Zone Id."""
        return self._zone_id

    @property
    def model(self) -> str:
        """Model."""
        return self._model

    @property
    def zone_name(self) -> str:
        """Zone Name."""
        return self._zone_name

    @property
    def lastseen(self) -> datetime:
        """Last Seen."""
        return self._lastseen

    @property
    def power(self) -> bool:
        """Power."""
        return self._power

    @property
    def volume(self) -> float:
        """Volume."""
        return self._volume

    @property
    def mute(self) -> bool:
        """Mute."""
        return self._mute

    @property
    def source(self) -> str:
        """Source."""
        return self._source

    async def set_zone_power(self, power: bool) -> None:
        """Set Zone Power."""
        _LOGGER.log(logging.INFO, "ZONE set_zone_power: %s", str(power))
        await self._controller.turn_on_off(self._zone_id, str(power))
        self._power = power

    async def set_zone_volume(self, volume: int, HAVolume: float) -> None:
        """Set Zone Volume."""
        _LOGGER.log(logging.INFO, "set_zone_volume value to send: %s", str(volume))
        await self._controller.set_volume(self._zone_id, volume)
        _LOGGER.log(logging.INFO, "HA value1 :  %s", str(HAVolume))
        HAVolume = HAVolume / 100
        _LOGGER.log(logging.INFO, "HA value2:  %s", str(HAVolume))
        self._volume = HAVolume

    async def set_zone_mute(self, mute: bool) -> None:
        """Set Zone Mute."""
        _LOGGER.log(logging.INFO, "set_zone_mute")
        await self._controller.set_mute(self._zone_id, mute)
        self._mute = mute

    async def set_zone_source(self, source: str) -> None:
        """Set Zone Source."""
        _LOGGER.log(logging.INFO, "set_zone_source")
        await self._controller.set_source(self._zone_id, source)
        self._source = source

    def updateVolume(self, value: float):
        """Update Volume."""
        _LOGGER.log(logging.INFO, "updateVolume")
        _LOGGER.log(logging.INFO, "lea value:  %s", str(value))
        value = (((value / -1) - 80) / 0.8) * -1
        HAVolume = value / 100
        _LOGGER.log(logging.INFO, "HA value1 :  %s", str(value))
        _LOGGER.log(logging.INFO, "HA value2:  %s", str(HAVolume))
        self._volume = HAVolume

        self.update_lastseen()
        if self._update_callback and callable(self._update_callback):
            _LOGGER.log(logging.INFO, "callback")
            self._update_callback(self)

    def update(self, value: str, commandType: str):
        """Update zone."""
        _LOGGER.log(logging.INFO, "update")
        _LOGGER.log(logging.INFO, "commandType:  %s", str(commandType))
        _LOGGER.log(logging.INFO, "value:  %s", str(value))
        if commandType == "mute":
            _LOGGER.log(logging.INFO, "update mute:  %s", str(value))
            if value == "true":
                self._mute = True
            else:
                self._mute = True
        elif commandType == "power":
            _LOGGER.log(logging.INFO, "update power:  %s", str(value))
            if value == "true":
                self._power = True
            else:
                self._power = True
        self.update_lastseen()
        if self._update_callback and callable(self._update_callback):
            _LOGGER.log(logging.INFO, "callback")
            self._update_callback(self)

    def update_lastseen(self) -> None:
        """Update Last Seen."""
        self._lastseen = datetime.now()
        _LOGGER.log(logging.INFO, "last seen: %s", str(self._lastseen))

    def __str__(self) -> str:
        """Str."""
        result = f"<LeaZone id={self.zone_id}, lastseen={self._lastseen}, power={self._power}"
        return result + (
            f", volume={self._volume}, mute={self._mute}, source={self._source}>"
            if self._power
            else ">"
        )
