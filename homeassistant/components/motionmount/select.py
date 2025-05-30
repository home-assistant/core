"""Support for MotionMount numeric control."""

from datetime import timedelta
import logging
import socket

import motionmount

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MotionMountConfigEntry
from .const import DOMAIN, WALL_PRESET_NAME
from .entity import MotionMountEntity

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MotionMountConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    mm = entry.runtime_data

    async_add_entities([MotionMountPresets(mm, entry)], True)


class MotionMountPresets(MotionMountEntity, SelectEntity):
    """The presets of a MotionMount."""

    _attr_should_poll = True
    _attr_translation_key = "motionmount_preset"

    def __init__(
        self,
        mm: motionmount.MotionMount,
        config_entry: MotionMountConfigEntry,
    ) -> None:
        """Initialize Preset selector."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-preset"
        self._presets: list[motionmount.Preset] = []
        self._attr_current_option = None

    def _update_options(self, presets: list[motionmount.Preset]) -> None:
        """Convert presets to select options."""
        options = [f"{preset.index}: {preset.name}" for preset in presets]
        options.insert(0, WALL_PRESET_NAME)

        self._attr_options = options

    async def _ensure_connected(self) -> bool:
        """Make sure there is a connection with the MotionMount.

        Returns false if the connection failed to be ensured.
        """
        if self.mm.is_connected:
            return True
        try:
            await self.mm.connect()
        except (ConnectionError, TimeoutError, socket.gaierror):
            # We're not interested in exceptions here. In case of a failed connection
            # the try/except from the caller will report it.
            # The purpose of `_ensure_connected()` is only to make sure we try to
            # reconnect, where failures should not be logged each time
            return False

        # Check we're properly authenticated or be able to become so
        if not self.mm.is_authenticated:
            if self.pin is None:
                await self.mm.disconnect()
                self.config_entry.async_start_reauth(self.hass)
                return False
            await self.mm.authenticate(self.pin)
            if not self.mm.is_authenticated:
                self.pin = None
                await self.mm.disconnect()
                self.config_entry.async_start_reauth(self.hass)
                return False

        _LOGGER.debug("Successfully reconnected to MotionMount")
        return True

    async def async_update(self) -> None:
        """Get latest state from MotionMount."""
        if not await self._ensure_connected():
            return

        try:
            self._presets = await self.mm.get_presets()
        except (TimeoutError, socket.gaierror) as ex:
            _LOGGER.warning("Failed to communicate with MotionMount: %s", ex)
        else:
            self._update_options(self._presets)

    @property
    def current_option(self) -> str | None:
        """Get the current option."""
        # When the mount is moving we return the currently selected option
        if self.mm.is_moving:
            return self._attr_current_option

        # When the mount isn't moving we select the option that matches the current position
        self._attr_current_option = None
        if self.mm.extension == 0 and self.mm.turn == 0:
            self._attr_current_option = self._attr_options[0]  # Select Wall preset
        else:
            for preset in self._presets:
                if (
                    preset.extension == self.mm.extension
                    and preset.turn == self.mm.turn
                ):
                    self._attr_current_option = f"{preset.index}: {preset.name}"
                    break

        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Set the new option."""
        index = int(option[:1])
        try:
            await self.mm.go_to_preset(index)
        except (TimeoutError, socket.gaierror) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_communication",
            ) from ex
        else:
            self._attr_current_option = option
