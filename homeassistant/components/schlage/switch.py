"""Platform for Schlage switch integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from pyschlage.lock import Lock

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LockData, SchlageDataUpdateCoordinator
from .entity import SchlageEntity


@dataclass(frozen=True, kw_only=True)
class SchlageSwitchEntityDescription(SwitchEntityDescription):
    """Entity description for a Schlage switch."""

    on_fn: Callable[[Lock], None]
    off_fn: Callable[[Lock], None]
    value_fn: Callable[[Lock], bool]


SWITCHES: tuple[SchlageSwitchEntityDescription, ...] = (
    SchlageSwitchEntityDescription(
        key="beeper",
        translation_key="beeper",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_fn=lambda lock: lock.set_beeper(True),
        off_fn=lambda lock: lock.set_beeper(False),
        value_fn=lambda lock: lock.beeper_enabled,
    ),
    SchlageSwitchEntityDescription(
        key="lock_and_leve",
        translation_key="lock_and_leave",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_fn=lambda lock: lock.set_lock_and_leave(True),
        off_fn=lambda lock: lock.set_lock_and_leave(False),
        value_fn=lambda lock: lock.lock_and_leave_enabled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches based on a config entry."""
    coordinator: SchlageDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    def _add_new_locks(locks: dict[str, LockData]) -> None:
        async_add_entities(
            SchlageSwitch(
                coordinator=coordinator,
                description=description,
                device_id=device_id,
            )
            for device_id in locks
            for description in SWITCHES
        )

    _add_new_locks(coordinator.data.locks)
    coordinator.new_locks_callbacks.append(_add_new_locks)


class SchlageSwitch(SchlageEntity, SwitchEntity):
    """Schlage switch entity."""

    entity_description: SchlageSwitchEntityDescription

    def __init__(
        self,
        coordinator: SchlageDataUpdateCoordinator,
        description: SchlageSwitchEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize a SchlageSwitch."""
        super().__init__(coordinator=coordinator, device_id=device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{self.entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        return self.entity_description.value_fn(self._lock)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(
            partial(self.entity_description.on_fn, self._lock)
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(
            partial(self.entity_description.off_fn, self._lock)
        )
        await self.coordinator.async_request_refresh()
