"""Support for the Netatmo climate schedule selector."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import NETATMO_CREATE_TEMPERATURE_SET

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo temperature set number platform."""

    @callback
    def _create_temperature_set_number(
        data: dict, update_schedule_callback: Callable
    ) -> None:
        """Handle the creation of a temperature set number entity."""
        async_add_entities(
            [NetatmoTemperatureSetNumber(hass, data, update_schedule_callback)]
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_TEMPERATURE_SET, _create_temperature_set_number
        )
    )


class NetatmoTemperatureSetNumber(NumberEntity):
    """Representation of a Netatmo temperature set as a number entity."""

    def __init__(
        self, hass: HomeAssistant, data: dict, update_schedule_callback: Callable
    ) -> None:
        """Initialize the temperature set number entity."""
        self.hass = hass
        self._home_id = data["home_id"]
        self._schedule_id = data["schedule_id"]
        self._schedule_name = data["schedule_name"]
        self._temp_set_id = data["temp_set_id"]
        self._temp_set_name = data["temp_set_name"]
        self._room_id = data["room_id"]
        self._room_name = data["room_name"]
        self._update_schedule_callback = update_schedule_callback

        self._attr_name = (
            f"{self._schedule_name} {self._temp_set_name} {self._room_name} Temperature"
        )
        self._attr_unique_id = (
            f"{self._home_id}-{self._schedule_id}-{self._temp_set_id}-{self._room_id}"
        )

        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_value = data["therm_setpoint_temperature"]

        # Explicitly set the entity ID to avoid conflicts
        sanitized_temp_set_name = self._temp_set_name.lower().replace("+", "plus")
        sanitized_entity_id_part = slugify(
            f"{self._schedule_name}_{sanitized_temp_set_name}_{self._room_name}"
        )
        self.entity_id = f"number.{sanitized_entity_id_part}"

    async def async_set_native_value(self, value: float) -> None:
        """Set a new target temperature."""
        _LOGGER.debug(
            "Setting temperature for room %s temperature set %s and schedule %s in home %s to %s°C",
            self._room_id,
            self._temp_set_id,
            self._schedule_id,
            self._home_id,
            value,
        )

        # Update the temperature in the schedule
        self._update_schedule_callback(
            home_id=self._home_id,
            schedule_id=self._schedule_id,
            temp_set_id=self._temp_set_id,
            room_id=self._room_id,
            new_temperature=value,
        )

        # Update the local state
        self._attr_native_value = value
        self.async_write_ha_state()
