"""Support for the KIWI.KI lock platform."""

from __future__ import annotations

import logging
from typing import Any

from kiwiki import KiwiClient, KiwiException
import voluptuous as vol

from homeassistant.components.lock import (
    PLATFORM_SCHEMA as LOCK_PLATFORM_SCHEMA,
    LockEntity,
    LockState,
)
from homeassistant.const import (
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_TYPE = "hardware_type"
ATTR_PERMISSION = "permission"
ATTR_CAN_INVITE = "can_invite_others"

UNLOCK_MAINTAIN_TIME = 5

PLATFORM_SCHEMA = LOCK_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the KIWI lock platform."""

    try:
        kiwi = KiwiClient(config[CONF_USERNAME], config[CONF_PASSWORD])
    except KiwiException as exc:
        _LOGGER.error(exc)
        return
    if not (available_locks := kiwi.get_locks()):
        # No locks found; abort setup routine.
        _LOGGER.debug("No KIWI locks found in your account")
        return
    add_entities([KiwiLock(lock, kiwi) for lock in available_locks], True)


class KiwiLock(LockEntity):
    """Representation of a Kiwi lock."""

    def __init__(self, kiwi_lock, client):
        """Initialize the lock."""
        self._sensor = kiwi_lock
        self._client = client
        self.lock_id = kiwi_lock["sensor_id"]
        self._state = LockState.LOCKED

        address = kiwi_lock.get("address")
        address.update(
            {
                ATTR_LATITUDE: address.pop("lat", None),
                ATTR_LONGITUDE: address.pop("lng", None),
            }
        )

        self._device_attrs = {
            ATTR_ID: self.lock_id,
            ATTR_TYPE: kiwi_lock.get("hardware_type"),
            ATTR_PERMISSION: kiwi_lock.get("highest_permission"),
            ATTR_CAN_INVITE: kiwi_lock.get("can_invite"),
            **address,
        }

    @property
    def name(self) -> str | None:
        """Return the name of the lock."""
        name = self._sensor.get("name")
        specifier = self._sensor["address"].get("specifier")
        return name or specifier

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state == LockState.LOCKED

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        return self._device_attrs

    @callback
    def clear_unlock_state(self, _):
        """Clear unlock state automatically."""
        self._state = LockState.LOCKED
        self.async_write_ha_state()

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""

        try:
            self._client.open_door(self.lock_id)
        except KiwiException:
            _LOGGER.error("Failed to open door")
        else:
            self._state = LockState.UNLOCKED
            self.hass.add_job(
                async_call_later,
                self.hass,
                UNLOCK_MAINTAIN_TIME,
                self.clear_unlock_state,
            )
