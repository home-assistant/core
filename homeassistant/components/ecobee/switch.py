"""Support for using switch with ecobee thermostats."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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


@dataclass(frozen=True, kw_only=True)
class EcobeeSwitchEntityDescription(SwitchEntity):
    """Class describing Ecobee switch entities."""

    ecobee_setting_key: str
    set_fn: Callable[[EcobeeData, int, int], Awaitable]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat switch entity."""
    data: EcobeeData = hass.data[DOMAIN]
    _LOGGER.debug("Adding ventilators 20 min switch if present")

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

    def __init__(
        self,
        data: EcobeeData,
        thermostat_index: int,
    ) -> None:
        """Initialize ecobee ventilator platform."""
        super().__init__(data, thermostat_index)
        self._attr_unique_id = "ventilator_20m_timer"
        self._attr_native_value = False
        self._time_zone_delay = datetime.strptime(
            self.thermostat["utcTime"], DATE_FORMAT
        ) - datetime.strptime(self.thermostat["thermostatTime"], DATE_FORMAT)

    @property
    def is_on(self) -> bool:
        """Get the latest state from the thermostat."""
        return self._attr_native_value

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""
        await self.data.update()

        ventilatorOffDateTime = self.thermostat["settings"]["ventilatorOffDateTime"]

        self._attr_native_value = (
            ventilatorOffDateTime is not None
            and ventilatorOffDateTime != ""
            and datetime.strptime(ventilatorOffDateTime, DATE_FORMAT)
            + self._time_zone_delay
            >= datetime.now()
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set ventilator 20 min timer on."""
        await self.hass.async_add_executor_job(
            self.data.ecobee.set_ventilator_timer, self.thermostat_index, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set ventilator 20 min timer off."""
        await self.hass.async_add_executor_job(
            self.data.ecobee.set_ventilator_timer, self.thermostat_index, False
        )
