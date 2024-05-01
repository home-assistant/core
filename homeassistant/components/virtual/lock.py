"""Provide support for a virtual lock."""

from datetime import timedelta
import logging
import random
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.lock import DOMAIN as PLATFORM_DOMAIN, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_LOCKED
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import track_point_in_time
import homeassistant.util.dt as dt_util

from . import get_entity_configs
from .const import (
    ATTR_GROUP_NAME,
    COMPONENT_DOMAIN,
    COMPONENT_NETWORK,
    CONF_COORDINATED,
    CONF_INITIAL_VALUE,
    CONF_SIMULATE_NETWORK,
)
from .coordinator import VirtualDataUpdateCoordinator
from .entity import CoordinatedVirtualEntity, VirtualEntity, virtual_schema
from .network import NetworkProxy

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [COMPONENT_DOMAIN]

CONF_CHANGE_TIME = "locking_time"
CONF_TEST_JAMMING = "jamming_test"

DEFAULT_LOCK_VALUE = "locked"
DEFAULT_CHANGE_TIME = timedelta(seconds=0)
DEFAULT_TEST_JAMMING = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    virtual_schema(
        DEFAULT_LOCK_VALUE,
        {
            vol.Optional(CONF_CHANGE_TIME, default=DEFAULT_CHANGE_TIME): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
            vol.Optional(
                CONF_TEST_JAMMING, default=DEFAULT_TEST_JAMMING
            ): cv.positive_int,
        },
    )
)
LOCK_SCHEMA = vol.Schema(
    virtual_schema(
        DEFAULT_LOCK_VALUE,
        {
            vol.Optional(CONF_CHANGE_TIME, default=DEFAULT_CHANGE_TIME): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
            vol.Optional(
                CONF_TEST_JAMMING, default=DEFAULT_TEST_JAMMING
            ): cv.positive_int,
        },
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up locks."""

    coordinator: VirtualDataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][
        entry.entry_id
    ]
    entities: list[VirtualLock] = []
    for entity_config in get_entity_configs(
        hass, entry.data[ATTR_GROUP_NAME], PLATFORM_DOMAIN
    ):
        entity_config = LOCK_SCHEMA(entity_config)
        if entity_config[CONF_COORDINATED]:
            entity = cast(
                VirtualLock, CoordinatedVirtualLock(hass, entity_config, coordinator)
            )
        else:
            entity = VirtualLock(hass, entity_config)

        if entity_config[CONF_SIMULATE_NETWORK]:
            entity = cast(VirtualLock, NetworkProxy(entity))
            hass.data[COMPONENT_NETWORK][entity.entity_id] = entity

        entities.append(entity)

    async_add_entities(entities)


class VirtualLock(VirtualEntity, LockEntity):
    """Representation of a Virtual lock."""

    def __init__(self, hass, config):
        """Initialize the Virtual lock device."""
        super().__init__(config, PLATFORM_DOMAIN)

        self._hass = hass
        self._change_time = config.get(CONF_CHANGE_TIME)
        self._test_jamming = config.get(CONF_TEST_JAMMING)

        _LOGGER.info("VirtualLock: %s created", self.name)

    def _create_state(self, config):
        super()._create_state(config)

        self._attr_is_locked = config.get(CONF_INITIAL_VALUE).lower() == STATE_LOCKED

    def _restore_state(self, state, config):
        super()._restore_state(state, config)

        self._attr_is_locked = state.state == STATE_LOCKED

    def _lock(self) -> None:
        if self._test_jamming == 0 or random.randint(0, self._test_jamming) > 0:
            self._attr_is_locked = True
            self._attr_is_locking = False
            self._attr_is_unlocking = False
            self._attr_is_jammed = False
        else:
            self._jam()

    def _locking(self) -> None:
        self._attr_is_locked = False
        self._attr_is_locking = True
        self._attr_is_unlocking = False
        self._attr_is_jammed = False

    def _unlock(self) -> None:
        self._attr_is_locked = False
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_jammed = False

    def _unlocking(self) -> None:
        self._attr_is_locked = False
        self._attr_is_locking = False
        self._attr_is_unlocking = True
        self._attr_is_jammed = False

    def _jam(self) -> None:
        self._attr_is_locked = False
        self._attr_is_jammed = True

    async def _finish_operation(self, _point_in_time) -> None:
        if self.is_locking:
            self._lock()
        if self.is_unlocking:
            self._unlock()
        self.async_schedule_update_ha_state()

    def _start_operation(self):
        track_point_in_time(
            self._hass, self._finish_operation, dt_util.utcnow() + self._change_time
        )

    def lock(self, **kwargs: Any) -> None:
        """Lock."""
        if self._change_time == DEFAULT_CHANGE_TIME:
            self._lock()
        else:
            self._locking()
            self._start_operation()

    def unlock(self, **kwargs: Any) -> None:
        """Unlock."""
        if self._change_time == DEFAULT_CHANGE_TIME:
            self._unlock()
        else:
            self._unlocking()
            self._start_operation()

    def open(self, **kwargs: Any) -> None:
        """Open."""
        self.unlock()


class CoordinatedVirtualLock(CoordinatedVirtualEntity, VirtualLock):
    """Representation of a Virtual switch."""

    def __init__(self, hass, config, coordinator):
        """Initialize the Virtual switch device."""
        CoordinatedVirtualEntity.__init__(self, coordinator)
        VirtualLock.__init__(self, hass, config)
