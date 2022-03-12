"""Interfaces with the myLeviton API for Decora Smart WiFi products."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.fan import (
    PLATFORM_SCHEMA,
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .common import BaseDecoraWifiEntity, EntityTypes, _setup_platform

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Decora fan controllers."""

    _setup_platform(
        EntityTypes.FAN,
        DecoraWifiFanController,
        hass,
        config,
        add_entities,
        discovery_info,
    )


class DecoraWifiFanController(BaseDecoraWifiEntity, FanEntity):
    """Encapsulates functionality specific to Decora WiFi fan controllers."""

    PERCENTAGE_ATTRIB_KEY = "brightness"

    @property
    def speed_count(self) -> int:
        """Return the number of supported non-zero speeds."""

        return len(self.preset_modes) - 1

    @property
    def supported_features(self) -> int:
        """Return supported features."""

        if self._switch.canSetLevel:
            return SUPPORT_SET_SPEED | SUPPORT_PRESET_MODE
        return 0

    @property
    def preset_modes(self) -> list[str]:
        """Return the supported preset modes."""

        return ["Off", "Low", "Medium", "High", "Max"]

    @property
    def preset_mode(self) -> str:
        """Return the current preset name."""

        percentage = self._switch.brightness
        idx = int(percentage / self.percentage_step)
        return self.preset_modes[idx]

    @property
    def percentage(self) -> int:
        """Return the current percentage."""

        return int(self._switch.brightness)

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        """Turn the fan on."""

        attribs: dict[str, Any] = {"power": "ON"}

        if percentage is not None:
            attribs[self.PERCENTAGE_ATTRIB_KEY] = self._get_valid_percentage(percentage)
        elif preset_mode is not None:
            attribs[self.PERCENTAGE_ATTRIB_KEY] = self._preset_mode_to_percentage(
                preset_mode
            )

        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn on myLeviton switch")

    def set_percentage(self, percentage: int) -> None:
        """Update the fan's speed."""

        percentage = self._get_valid_percentage(percentage)
        if percentage == 0:
            self.turn_off()
        else:
            self.turn_on(percentage=percentage)

    def _get_valid_percentage(self, percentage: int) -> int:
        """Get the nearest valid fan speed."""

        return percentage * round(percentage / self.percentage_step)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Update the fan's speed based on a preset."""

        if preset_mode == self.preset_modes[0]:
            self.turn_off()
        else:
            self.turn_on(preset_mode=preset_mode)

    def _preset_mode_to_percentage(self, preset_mode: str) -> int:
        """Convert a preset mode to a percentage."""

        if preset_mode not in self.preset_modes:
            return 0

        return int(self.preset_modes.index(preset_mode) * self.percentage_step)
