"""Support for Yale Lock."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    CONF_CODE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_VIA_DEVICE, COORDINATOR, DOMAIN, LOGGER, MANUFACTURER, MODEL
from .coordinator import YaleDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale lock entry."""
    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    async_add_entities(
        YaleDoorlock(coordinator, key) for key in coordinator.data["locks"]
    )


class YaleDoorlock(CoordinatorEntity, LockEntity):
    """Representation of a Yale doorlock."""

    def __init__(
        self, coordinator: YaleDataUpdateCoordinator, key: dict[str, Any]
    ) -> None:
        """Initialize the Yale Alarm Device."""
        self.coordinator = coordinator
        self._key = key
        self._attr_name: str = key["name"]
        self._attr_unique_id: str = key["address"].replace(":", "")
        self._attr_is_locked: bool = self._key["_state"] == "locked"
        self._attr_code_format: str = "^\\d{6}$"
        self._identifier: str = coordinator.entry.data[CONF_USERNAME]
        self._code: str | None = coordinator.entry.options.get(CONF_CODE)
        super().__init__(self.coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            ATTR_NAME: self._attr_name,
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: MODEL,
            ATTR_IDENTIFIERS: {(DOMAIN, self._attr_unique_id)},
            ATTR_VIA_DEVICE: (DOMAIN, self._identifier),
        }

    def unlock(self, **kwargs) -> None:
        """Send unlock command."""
        code = kwargs.get(ATTR_CODE, self._code)
        if code is None:
            LOGGER.error("Code required but none provided")

        self.set_lock_state(code, "unlock")

    def lock(self, **kwargs) -> None:
        """Send lock command."""
        self.set_lock_state("", "lock")

    def set_lock_state(self, code: str, state: str) -> None:
        """Send set lock state command."""
        get_lock = self.coordinator.yale.lock_api.get(self.name)  # type: ignore[attr-defined]

        if state == "lock":
            self.coordinator.yale.lock_api.close_lock(get_lock)  # type: ignore[attr-defined]
        if state == "unlock":
            self.coordinator.yale.lock_api.open_lock(get_lock, code)  # type: ignore[attr-defined]
