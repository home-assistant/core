"""Component provides basic support for Foscam IP cameras."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FoscamCoordinator
from .const import DOMAIN, LOGGER
from .entity import FoscamEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up foscam switch from a config entry."""

    coordinator: FoscamCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    await coordinator.async_config_entry_first_refresh()

    if coordinator.data["is_asleep"]["supported"]:
        async_add_entities([FoscamAwakeSwitch(coordinator, config_entry)])


class FoscamAwakeSwitch(FoscamEntity, SwitchEntity):
    """An implementation of a Foscam IP camera."""

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a Foscam camera."""
        super().__init__(coordinator, config_entry.entry_id)

        self._attr_name = config_entry.title + " Awake"
        self._attr_unique_id = config_entry.entry_id + "_awake_switch"

        self.is_asleep = self.coordinator.data["is_asleep"]["status"]

    @property
    def is_on(self):
        """Return true if switch is on."""
        return not self.is_asleep

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        LOGGER.debug("Wake camera")

        ret, _ = await self.hass.async_add_executor_job(
            self.coordinator.session.wake_up
        )

        if ret != 0:
            LOGGER.error("Error waking up: %s", ret)
            return

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        LOGGER.debug("Sleep camera")

        ret, _ = await self.hass.async_add_executor_job(self.coordinator.session.sleep)

        if ret != 0:
            LOGGER.error("Error sleeping: %s", ret)
            return

        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self.is_asleep = self.coordinator.data["is_asleep"]["status"]

        self.async_write_ha_state()
