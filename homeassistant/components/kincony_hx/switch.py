"""WiZ integration switch platform."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KCBoard, KCSwitch
from .const import CONF_REFRESH, DATA_KCBOARD, DEFAULT_REFRESH, DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KinCony switch platform."""
    board: KCBoard = hass.data[DOMAIN][entry.entry_id][DATA_KCBOARD]
    relays_len = board.read_relays_count()

    refresh_interval: int = (
        entry.data[CONF_REFRESH] if hasattr(entry, CONF_REFRESH) else DEFAULT_REFRESH
    )

    switches: list[KCSwitchEntity] = []
    for i in range(relays_len):
        switches.append(KCSwitchEntity(board, i, refresh_interval))

    async_add_entities(switches, True)


class KCSwitchEntity(KCSwitch, SwitchEntity):
    """Representation of KinCony Relay switch."""

    _cached_last_refresh_time: datetime
    _refresh_interval: int

    def __init__(
        self, board: KCBoard, index: int, refresh_interval: int, name: str = None
    ) -> None:
        """Create the entity."""
        super().__init__(board, index)
        self._attr_unique_id = self.get_uuid()
        self._attr_name = name if name is not None else f"SW {index + 1:02d}"
        self._attr_is_on = False
        self._refresh_interval = refresh_interval

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._board.write_relay_status(self._index, True)
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._board.write_relay_status(self._index, False)
        self._attr_is_on = False

    def update(self) -> None:
        """Fetch from cache or live the latest state for this relay."""

        now = datetime.utcnow()
        if not hasattr(
            self, "_cached_last_refresh_time"
        ) or now - self._cached_last_refresh_time > timedelta(
            seconds=self._refresh_interval
        ):
            self._cached_last_refresh_time = now
            self._attr_is_on = self._board.read_relay_status(self._index)
