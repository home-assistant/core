"""Representation of Z-Wave locks."""
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import (
    LOCK_CMD_CLASS_TO_LOCKED_STATE_MAP,
    LOCK_CMD_CLASS_TO_PROPERTY_MAP,
    CommandClass,
    DoorLockMode,
)
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)

STATE_TO_ZWAVE_MAP: Dict[int, Dict[str, Union[int, bool]]] = {
    CommandClass.DOOR_LOCK: {
        STATE_UNLOCKED: DoorLockMode.UNSECURED,
        STATE_LOCKED: DoorLockMode.SECURED,
    },
    CommandClass.LOCK: {
        STATE_UNLOCKED: False,
        STATE_LOCKED: True,
    },
}


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave lock from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_lock(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Lock."""
        entities: List[ZWaveBaseEntity] = []
        entities.append(ZWaveLock(config_entry, client, info))

        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_{config_entry.entry_id}_add_{LOCK_DOMAIN}", async_add_lock
        )
    )


class ZWaveLock(ZWaveBaseEntity, LockEntity):
    """Representation of a Z-Wave lock."""

    @property
    def is_locked(self) -> Optional[bool]:
        """Return true if the lock is locked."""
        return int(
            LOCK_CMD_CLASS_TO_LOCKED_STATE_MAP[
                CommandClass(self.info.primary_value.command_class)
            ]
        ) == int(self.info.primary_value.value)

    async def _set_lock_state(
        self, target_state: str, **kwargs: Dict[str, Any]
    ) -> None:
        """Set the lock state."""
        target_value: ZwaveValue = self.get_zwave_value(
            LOCK_CMD_CLASS_TO_PROPERTY_MAP[self.info.primary_value.command_class]
        )
        if target_value is not None:
            await self.info.node.async_set_value(
                target_value,
                STATE_TO_ZWAVE_MAP[self.info.primary_value.command_class][target_state],
            )

    async def async_lock(self, **kwargs: Dict[str, Any]) -> None:
        """Lock the lock."""
        await self._set_lock_state(STATE_LOCKED)

    async def async_unlock(self, **kwargs: Dict[str, Any]) -> None:
        """Unlock the lock."""
        await self._set_lock_state(STATE_UNLOCKED)
