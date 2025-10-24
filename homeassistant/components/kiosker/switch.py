"""Switch platform for Kiosker."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KioskerConfigEntry
from .coordinator import KioskerDataUpdateCoordinator
from .entity import KioskerEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KioskerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kiosker switch based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([KioskerScreensaverSwitch(coordinator)])


class KioskerScreensaverSwitch(KioskerEntity, SwitchEntity):
    """Screensaver disable switch for Kiosker."""

    _attr_has_entity_name = True
    _attr_translation_key = "disable_screensaver"

    def __init__(self, coordinator: KioskerDataUpdateCoordinator) -> None:
        """Initialize the screensaver switch."""

        super().__init__(coordinator)

        device_id = self._get_device_id()
        self._attr_unique_id = f"{device_id}_{self._attr_translation_key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if screensaver is disabled."""
        if self.coordinator.data and "screensaver" in self.coordinator.data:
            screensaver_state = self.coordinator.data["screensaver"]
            if hasattr(screensaver_state, "disabled"):
                return screensaver_state.disabled
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on (disable screensaver)."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.api.screensaver_set_disabled_state, True
            )
            await self.coordinator.async_request_refresh()
        except (OSError, TimeoutError) as exc:
            _LOGGER.error(
                "Failed to disable screensaver on device %s: %s",
                self.coordinator.api.host,
                exc,
            )
            raise
        except Exception as exc:
            _LOGGER.error(
                "Unexpected error disabling screensaver on device %s: %s",
                self.coordinator.api.host,
                exc,
            )
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off (enable screensaver)."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.api.screensaver_set_disabled_state, False
            )
            await self.coordinator.async_request_refresh()
        except (OSError, TimeoutError) as exc:
            _LOGGER.error(
                "Failed to enable screensaver on device %s: %s",
                self.coordinator.api.host,
                exc,
            )
            raise
        except Exception as exc:
            _LOGGER.error(
                "Unexpected error enabling screensaver on device %s: %s",
                self.coordinator.api.host,
                exc,
            )
            raise
