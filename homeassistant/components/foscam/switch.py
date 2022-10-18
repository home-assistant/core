"""This component provides basic support for Foscam IP cameras."""
from __future__ import annotations

from typing import Any

from libpyfoscam import FoscamCamera

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FoscamCoordinator
from .const import DOMAIN, LOGGER
from .entity import FoscamCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up foscam switch from a config entry."""

    session: FoscamCamera = hass.data[DOMAIN][config_entry.entry_id]["session"]
    coordinator: FoscamCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([FoscamAwakeSwitch(session, coordinator, config_entry)])


class FoscamAwakeSwitch(FoscamCoordinatorEntity, SwitchEntity):
    """An implementation of a Foscam IP camera."""

    def __init__(
        self,
        session: FoscamCamera,
        coordinator: FoscamCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a Foscam camera."""
        super().__init__(session, coordinator, config_entry)

        self._attr_name = "Awake"
        self._attr_unique_id = config_entry.entry_id + "_awake_switch"

        self.is_asleep = False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return not self.is_asleep

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        LOGGER.debug("Wake camera %s", self._name)

        ret, _ = await self.hass.async_add_executor_job(self._foscam_session.wake_up)

        if ret != 0:
            LOGGER.error("Error waking up '%s': %s", self._name, ret)
            return

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        LOGGER.debug("Sleep camera %s", self._name)

        ret, _ = await self.hass.async_add_executor_job(self._foscam_session.sleep)

        if ret != 0:
            LOGGER.error("Error sleeping '%s': %s", self._name, ret)
            return

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self.is_asleep = self.coordinator.data["is_asleep"]

        self.async_write_ha_state()
