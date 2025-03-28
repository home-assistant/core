"""LEA Zone Structure."""

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

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
        self._power: bool = False
        self._volume: int = 0
        self._mute: bool = False
        self._source: int = 0
        self._update_callback: Callable[[LeaZone], None] | None = None
        self.is_manual: bool = False

    def updatePower(self, value: bool) -> None:
        """Update zone."""
        _LOGGER.log(logging.INFO, "set_zone_power: %s", str(value))
        self._power = value
        self.update_lastseen()
        if self._update_callback and callable(self._update_callback):
            self._update_callback(self)

    def updateVolume(self, value: int) -> None:
        """Update zone."""
        self._volume = value
        self.update_lastseen()
        if self._update_callback and callable(self._update_callback):
            self._update_callback(self)

    def updateMute(self, value: bool) -> None:
        """Update zone."""
        self._mute = value
        self.update_lastseen()
        if self._update_callback and callable(self._update_callback):
            self._update_callback(self)

    def updateSource(self, value: int) -> None:
        """Update zone."""
        self._source = value
        self.update_lastseen()
        if self._update_callback and callable(self._update_callback):
            self._update_callback(self)

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
    def volume(self) -> int:
        """Volume."""
        return self._volume

    @property
    def mute(self) -> bool:
        """Mute."""
        return self._mute

    @property
    def source(self) -> int:
        """Source."""
        return self._source

    @property
    def update_callback(self):
        """Update Callback."""
        return self._update_callback

    def set_update_callback(self, update_callback):
        """Set Update Callback."""
        old_callback = self._update_callback
        self._update_callback = update_callback
        return old_callback

    async def set_zone_power(self, power: bool):
        """Set Zone Power."""
        _LOGGER.log(logging.INFO, "set_zone_power: %s", str(power))
        self._power = power

    async def set_zone_volume(self, volume: int):
        """Set Zone Volume."""
        _LOGGER.log(logging.INFO, "set_zone_volume: %s", str(volume))
        self._volume = volume

    async def set_zone_mute(self, mute: bool):
        """Set Zone Mute."""
        _LOGGER.debug("set_zone_mute")
        self._mute = mute

    async def set_zone_source(self, source: int):
        """Set Zone Source."""
        _LOGGER.debug("set_zone_source")
        self._source = source

    def update_lastseen(self):
        """Update Last Seen."""
        self._lastseen = datetime.now()

    def as_dict(self) -> dict[str, Any]:
        """Dictinory."""
        return {
            "zoneId": self._zone_id,
            "power": self._power,
            "volume": self._volume,
            "mute": self._mute,
            "source": self._source,
        }

    def __str__(self) -> str:
        """Str."""
        result = f"<LeaZone id={self.zone_id}, lastseen={self._lastseen}, power={self._power}"
        return result + (
            f", volume={self._volume}, mute={self._mute}, source={self._source}>"
            if self._power
            else ">"
        )
