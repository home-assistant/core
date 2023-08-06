"""Platform for Schlage switch integration."""

from __future__ import annotations

from functools import partial
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SchlageDataUpdateCoordinator
from .entity import SchlageEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches based on a config entry."""
    coordinator: SchlageDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for device_id in coordinator.data.locks:
        entities.extend(
            [
                BeeperSwitch(coordinator=coordinator, device_id=device_id),
                LockAndLeaveSwitch(coordinator=coordinator, device_id=device_id),
            ]
        )
    async_add_entities(entities)


class BeeperSwitch(SchlageEntity, SwitchEntity):
    """Schlage keypad beeper switch."""

    entity_description = SwitchEntityDescription(
        key="beeper",
        translation_key="beeper",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(
        self,
        coordinator: SchlageDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize a BeeperSwitch."""
        super().__init__(coordinator=coordinator, device_id=device_id)
        self._attr_unique_id = f"{device_id}_{self.entity_description.key}"
        self._attr_is_on = self._lock.beeper_enabled

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self._lock.beeper_enabled
        return super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the keypad beeper on."""
        await self.hass.async_add_executor_job(partial(self._lock.set_beeper, True))
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the keypad beeper off."""
        await self.hass.async_add_executor_job(partial(self._lock.set_beeper, False))
        await self.coordinator.async_request_refresh()


class LockAndLeaveSwitch(SchlageEntity, SwitchEntity):
    """Schlage lock-and-leave switch."""

    entity_description = SwitchEntityDescription(
        key="lock_and_leve",
        translation_key="lock_and_leave",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(
        self,
        coordinator: SchlageDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize a LockAndLeaveSwitch."""
        super().__init__(coordinator=coordinator, device_id=device_id)
        self._attr_unique_id = f"{device_id}_{self.entity_description.key}"
        self._attr_is_on = self._lock.lock_and_leave_enabled

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self._lock.lock_and_leave_enabled
        return super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn lock-and-leave on."""
        await self.hass.async_add_executor_job(
            partial(self._lock.set_lock_and_leave, True)
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn lock-and-leave off."""
        await self.hass.async_add_executor_job(
            partial(self._lock.set_lock_and_leave, False)
        )
        await self.coordinator.async_request_refresh()
