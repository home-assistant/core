"""Support for using switch with ecobee thermostats."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcobeeData
from .const import DOMAIN
from .entity import EcobeeBaseEntity

_LOGGER = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat switch entity."""
    data: EcobeeData = hass.data[DOMAIN]

    async_add_entities(
        (
            EcobeeVentilator20MinSwitch(data, index)
            for index, thermostat in enumerate(data.ecobee.thermostats)
            if thermostat["settings"]["ventilatorType"] != "none"
        ),
        True,
    )


class EcobeeVentilator20MinSwitch(EcobeeBaseEntity, SwitchEntity):
    """A Switch class, representing 20 min timer for an ecobee thermostat with ventilator attached."""

    _attr_has_entity_name = True
    _attr_name = "Ventilator 20m Timer"

    def __init__(
        self,
        data: EcobeeData,
        thermostat_index: int,
    ) -> None:
        """Initialize ecobee ventilator platform."""
        super().__init__(data, thermostat_index)
        self._attr_unique_id = f"{self.base_unique_id}_ventilator_20m_timer"
        self._attr_is_on = False
        self.update_without_throttle = False

    @property
    def is_on(self) -> bool | None:
        """Get the latest state from the thermostat."""
        return self._attr_is_on

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""

        if self.update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            await self.data.update()

        ventilator_off_date_time = self.thermostat["settings"]["ventilatorOffDateTime"]

        time_zone_delay = datetime.strptime(
            self.thermostat["utcTime"], DATE_FORMAT
        ) - datetime.strptime(self.thermostat["thermostatTime"], DATE_FORMAT)

        self._attr_is_on = (
            ventilator_off_date_time is not None
            and ventilator_off_date_time != ""
            and datetime.strptime(ventilator_off_date_time, DATE_FORMAT)
            + time_zone_delay
            >= datetime.now()
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set ventilator 20 min timer on."""
        await self.hass.async_add_executor_job(
            self.data.ecobee.set_ventilator_timer, self.thermostat_index, True
        )
        self.update_without_throttle = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set ventilator 20 min timer off."""
        await self.hass.async_add_executor_job(
            self.data.ecobee.set_ventilator_timer, self.thermostat_index, False
        )
        self.update_without_throttle = True
