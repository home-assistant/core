"""Vacuum platform for Eufy RoboVac."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_LOCAL_KEY
from .model_mappings import MODEL_MAPPINGS, RoboVacModelMapping

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eufy RoboVac entities from a config entry."""
    model_code: str = entry.data[CONF_MODEL]
    mapping = MODEL_MAPPINGS[model_code]

    async_add_entities([EufyRoboVacEntity(entry=entry, mapping=mapping)])


class EufyRoboVacEntity(StateVacuumEntity):
    """Representation of a Eufy RoboVac vacuum entity.

    This is intentionally a minimal spike implementation for model-first wiring.
    Cloud/local protocol execution is added in later iterations.
    """

    _attr_should_poll = False

    def __init__(self, *, entry: ConfigEntry, mapping: RoboVacModelMapping) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._mapping = mapping

        self._attr_unique_id = entry.data[CONF_ID]
        self._attr_name = entry.data[CONF_NAME]
        self._attr_activity = VacuumActivity.IDLE
        self._attr_fan_speed = "standard"
        self._attr_fan_speed_list = list(mapping.fan_speed_values)
        self._attr_supported_features = (
            VacuumEntityFeature.START
            | VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.FAN_SPEED
            | VacuumEntityFeature.SEND_COMMAND
            | VacuumEntityFeature.LOCATE
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "model_code": self._mapping.model_code,
            "model_name": self._mapping.display_name,
            "host": self._entry.data[CONF_HOST],
            "local_key_present": bool(self._entry.data.get(CONF_LOCAL_KEY)),
        }

    async def async_start(self) -> None:
        """Start cleaning."""
        self._attr_activity = VacuumActivity.CLEANING
        self.async_write_ha_state()

    async def async_pause(self) -> None:
        """Pause cleaning."""
        self._attr_activity = VacuumActivity.PAUSED
        self.async_write_ha_state()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop cleaning."""
        self._attr_activity = VacuumActivity.IDLE
        self.async_write_ha_state()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return to dock."""
        self._attr_activity = VacuumActivity.RETURNING
        self.async_write_ha_state()

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum."""
        _LOGGER.debug("Locate requested for %s", self._attr_unique_id)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if fan_speed not in self._mapping.fan_speed_values:
            _LOGGER.warning(
                "Unsupported fan speed requested for %s: %s",
                self._attr_unique_id,
                fan_speed,
            )
            return

        self._attr_fan_speed = fan_speed
        self.async_write_ha_state()

    async def async_send_command(
        self, command: str, params: list[str] | None = None, **kwargs: Any
    ) -> None:
        """Send a command to the vacuum.

        Supported in this spike: mapped cleaning mode names via `command`.
        """
        if command not in self._mapping.mode_values:
            _LOGGER.warning(
                "Unsupported send_command for %s: %s (params=%s)",
                self._attr_unique_id,
                command,
                params,
            )
            return

        _LOGGER.debug(
            "send_command mapped for %s: %s -> %s",
            self._attr_unique_id,
            command,
            self._mapping.mode_values[command],
        )
