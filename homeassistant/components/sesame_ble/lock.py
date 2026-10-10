"""Platform for Sesame BLE lock integration."""

from collections.abc import Callable
from typing import Any, override

from pysesame_ble import SesameLock

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SesameBleConfigEntry, SesameDeviceWrapper
from .const import DOMAIN, FRIENDLY_MODELS

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SesameBleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lock entity for Candy House Sesame BLE lock."""
    wrapper: SesameDeviceWrapper = entry.runtime_data
    async_add_entities([SesameBLELock(wrapper)])


class SesameBLELock(LockEntity):
    """Representation of a Candy House Sesame BLE lock."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, wrapper: SesameDeviceWrapper) -> None:
        """Initialize the lock."""
        self.wrapper = wrapper
        self.sesame: SesameLock = wrapper.device
        self._attr_name = None
        self._attr_unique_id = wrapper.entry.unique_id

        self._unregister_status_callback: Callable[[], None] | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks when added to Home Assistant."""
        self._unregister_status_callback = self.wrapper.register_update_listener(
            self.async_write_ha_state
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when removed."""
        if self._unregister_status_callback:
            self._unregister_status_callback()

    @property
    @override
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        return self.sesame.is_locked

    @property
    @override
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        return bool(
            self.sesame.is_moving
            and self.sesame.target_angle is not None
            and self.sesame.target_angle == self.sesame.lock_position
        )

    @property
    @override
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return bool(
            self.sesame.is_moving
            and self.sesame.target_angle is not None
            and self.sesame.target_angle == self.sesame.unlock_position
        )

    @property
    @override
    def available(self) -> bool:
        """Return true if the device is available."""
        return self.wrapper.available

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information about this Sesame lock."""
        friendly_model = FRIENDLY_MODELS.get(
            self.wrapper.model_name, self.wrapper.model_name
        )
        unique_id = self.wrapper.entry.unique_id or self.wrapper.mac_address
        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self.wrapper.entry.title,
            manufacturer="CANDY HOUSE",
            model=friendly_model,
            connections={(CONNECTION_BLUETOOTH, self.wrapper.mac_address)},
        )

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        try:
            if not self.sesame.is_logged_in:
                await self.wrapper.async_connect()
            await self.sesame.lock(history_name="Home Assistant")
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_failed",
                translation_placeholders={
                    "address": getattr(
                        self.wrapper.ble_device, "address", self.wrapper.mac_address
                    ),
                    "error": str(err),
                },
            ) from err

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        try:
            if not self.sesame.is_logged_in:
                await self.wrapper.async_connect()
            await self.sesame.unlock(history_name="Home Assistant")
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unlock_failed",
                translation_placeholders={
                    "address": getattr(
                        self.wrapper.ble_device, "address", self.wrapper.mac_address
                    ),
                    "error": str(err),
                },
            ) from err
