"""Base entity class for Schlage."""

from collections.abc import Callable
from typing import Any, override

from pyschlage.exceptions import Error as SchlageError
from pyschlage.lock import Lock

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import LockData, SchlageDataUpdateCoordinator


class SchlageEntity(CoordinatorEntity[SchlageDataUpdateCoordinator]):
    """Base Schlage entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SchlageDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a Schlage entity."""
        super().__init__(coordinator=coordinator)
        self.device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self._lock.name,
            manufacturer=MANUFACTURER,
            model=self._lock.model_name,
            sw_version=self._lock.firmware_version,
        )

    @property
    def _lock_data(self) -> LockData:
        """Fetch the LockData from our coordinator."""
        return self.coordinator.data[self.device_id]

    @property
    def _lock(self) -> Lock:
        """Fetch the Schlage lock from our coordinator."""
        return self._lock_data.lock

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.device_id in self.coordinator.data
            and self._lock.connected
        )

    async def _async_send_command(self, func: Callable[..., Any], *args: Any) -> None:
        """Send a command to the lock, translating library errors."""
        try:
            await self.hass.async_add_executor_job(func, *args)
        except SchlageError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="schlage_command_failed"
            ) from ex
