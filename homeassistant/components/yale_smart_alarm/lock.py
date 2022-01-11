"""Lock for Yale Alarm."""
from __future__ import annotations

from typing import TYPE_CHECKING

from yalesmartalarmclient.exceptions import AuthenticationError, UnknownError

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, CONF_CODE, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_LOCK_CODE_DIGITS,
    COORDINATOR,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    MODEL,
)
from .coordinator import YaleDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale lock entry."""

    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    code_format = entry.options.get(CONF_LOCK_CODE_DIGITS, DEFAULT_LOCK_CODE_DIGITS)

    async_add_entities(
        YaleDoorlock(coordinator, data, code_format)
        for data in coordinator.data["locks"]
    )


class YaleDoorlock(CoordinatorEntity, LockEntity):
    """Representation of a Yale doorlock."""

    def __init__(
        self, coordinator: YaleDataUpdateCoordinator, data: dict, code_format: int
    ) -> None:
        """Initialize the Yale Lock Device."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_name = data["name"]
        self._attr_unique_id = data["address"]
        self._attr_device_info = DeviceInfo(
            name=self._attr_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            identifiers={(DOMAIN, data["address"])},
            via_device=(DOMAIN, self._coordinator.entry.data[CONF_USERNAME]),
        )
        self._attr_code_format = f"^\\d{code_format}$"

    async def async_unlock(self, **kwargs) -> None:
        """Send unlock command."""
        if TYPE_CHECKING:
            assert self._coordinator.yale, "Connection to API is missing"

        code = kwargs.get(ATTR_CODE, self._coordinator.entry.options.get(CONF_CODE))

        if not code:
            raise HomeAssistantError(
                f"No code provided, {self._attr_name} not unlocked"
            )

        try:
            get_lock = await self.hass.async_add_executor_job(
                self._coordinator.yale.lock_api.get, self._attr_name
            )
            lock_state = await self.hass.async_add_executor_job(
                self._coordinator.yale.lock_api.open_lock,
                get_lock,
                code,
            )
        except (
            AuthenticationError,
            ConnectionError,
            TimeoutError,
            UnknownError,
        ) as error:
            raise HomeAssistantError(
                f"Could not verify unlocking for {self._attr_name}: {error}"
            ) from error

        LOGGER.debug("Door unlock: %s", lock_state)
        if lock_state:
            for lock in self.coordinator.data["locks"]:
                if lock["address"] == self._attr_unique_id:
                    lock["_state"] = "unlocked"
                    LOGGER.debug("lock data %s", self.coordinator.data["locks"])
            self.async_write_ha_state()
            return
        raise HomeAssistantError("Could not unlock, check system ready for unlocking")

    async def async_lock(self, **kwargs) -> None:
        """Send lock command."""
        if TYPE_CHECKING:
            assert self._coordinator.yale, "Connection to API is missing"

        try:
            get_lock = await self.hass.async_add_executor_job(
                self._coordinator.yale.lock_api.get, self._attr_name
            )
            lock_state = await self.hass.async_add_executor_job(
                self._coordinator.yale.lock_api.close_lock,
                get_lock,
            )
        except (
            AuthenticationError,
            ConnectionError,
            TimeoutError,
            UnknownError,
        ) as error:
            raise HomeAssistantError(
                f"Could not verify unlocking for {self._attr_name}: {error}"
            ) from error

        LOGGER.debug("Door unlock: %s", lock_state)
        if lock_state:
            for lock in self.coordinator.data["locks"]:
                if lock["address"] == self._attr_unique_id:
                    lock["_state"] = "locked"
            self.async_write_ha_state()
            return
        raise HomeAssistantError("Could not unlock, check system ready for unlocking")

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        for lock in self.coordinator.data["locks"]:
            return bool(
                lock["address"] == self._attr_unique_id and lock["_state"] == "locked"
            )
        return None
