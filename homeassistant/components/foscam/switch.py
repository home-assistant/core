"""Component provides support for the Foscam Switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import FoscamConfigEntry, FoscamCoordinator
from .entity import FoscamEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FoscamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up foscam switch from a config entry."""

    coordinator = config_entry.runtime_data

    await coordinator.async_config_entry_first_refresh()

    if coordinator.data["is_asleep"]["supported"]:
        async_add_entities([FoscamSleepSwitch(coordinator, config_entry)])


class FoscamSleepSwitch(FoscamEntity, SwitchEntity):
    """An implementation for Sleep Switch."""

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        config_entry: FoscamConfigEntry,
    ) -> None:
        """Initialize a Foscam Sleep Switch."""
        super().__init__(coordinator, config_entry.entry_id)

        self._attr_unique_id = f"{config_entry.entry_id}_sleep_switch"
        self._attr_translation_key = "sleep_switch"
        self._attr_has_entity_name = True

        self.is_asleep = self.coordinator.data["is_asleep"]["status"]

    @property
    def is_on(self):
        """Return true if camera is asleep."""
        return self.is_asleep

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Wake camera."""
        LOGGER.debug("Wake camera")

        ret, _ = await self.hass.async_add_executor_job(
            self.coordinator.session.wake_up
        )

        if ret != 0:
            raise HomeAssistantError(f"Error waking up: {ret}")

        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """But camera is sleep."""
        LOGGER.debug("Sleep camera")

        ret, _ = await self.hass.async_add_executor_job(self.coordinator.session.sleep)

        if ret != 0:
            raise HomeAssistantError(f"Error sleeping: {ret}")

        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self.is_asleep = self.coordinator.data["is_asleep"]["status"]

        self.async_write_ha_state()
