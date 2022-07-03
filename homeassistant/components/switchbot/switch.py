"""Support for Switchbot bot."""
from __future__ import annotations

import logging
from typing import Any

from switchbot import Switchbot

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import entity_platform
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_RETRY_COUNT, DATA_COORDINATOR, DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

# Initialize the logger
_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    if not coordinator.data.get(entry.unique_id):
        raise PlatformNotReady

    async_add_entities(
        [
            SwitchBotBotEntity(
                coordinator,
                entry.unique_id,
                entry.data[CONF_MAC],
                entry.data[CONF_NAME],
                coordinator.switchbot_api.Switchbot(
                    mac=entry.data[CONF_MAC],
                    password=entry.data.get(CONF_PASSWORD),
                    retry_count=entry.options[CONF_RETRY_COUNT],
                ),
            )
        ]
    )


class SwitchBotBotEntity(SwitchbotEntity, SwitchEntity, RestoreEntity):
    """Representation of a Switchbot."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        idx: str | None,
        mac: str,
        name: str,
        device: Switchbot,
    ) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator, idx, mac, name)
        self._attr_unique_id = idx
        self._device = device
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON
        self._last_run_success = last_state.attributes["last_run_success"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        _LOGGER.info("Turn Switchbot bot on %s", self._mac)

        self._last_run_success = bool(await self._device.turn_on())
        if self._last_run_success:
            self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        _LOGGER.info("Turn Switchbot bot off %s", self._mac)

        self._last_run_success = bool(await self._device.turn_off())
        if self._last_run_success:
            self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        if not self.data["data"]["switchMode"]:
            return True
        return False

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        if not self.data["data"]["switchMode"]:
            return self._attr_is_on
        return self.data["data"]["isOn"]

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            **super().extra_state_attributes,
            "switch_mode": self.data["data"]["switchMode"],
        }
