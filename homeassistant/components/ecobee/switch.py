"""Support for using switch with ecobee thermostats."""

from __future__ import annotations

from datetime import tzinfo
import logging
from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import EcobeeConfigEntry, EcobeeData
from .climate import HASS_TO_ECOBEE_HVAC
from .const import ECOBEE_AUX_HEAT_ONLY
from .entity import EcobeeBaseEntity

_LOGGER = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcobeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat switch entity."""
    data = config_entry.runtime_data

    entities: list[SwitchEntity] = [
        EcobeeVentilator20MinSwitch(
            data,
            index,
            (await dt_util.async_get_time_zone(thermostat["location"]["timeZone"]))
            or dt_util.get_default_time_zone(),
        )
        for index, thermostat in enumerate(data.ecobee.thermostats)
        if thermostat["settings"]["ventilatorType"] != "none"
    ]

    entities.extend(
        (
            EcobeeSwitchAuxHeatOnly(data, index)
            for index, thermostat in enumerate(data.ecobee.thermostats)
            if thermostat["settings"]["hasHeatPump"]
        )
    )

    async_add_entities(entities, update_before_add=True)


class EcobeeVentilator20MinSwitch(EcobeeBaseEntity, SwitchEntity):
    """A Switch class, representing 20 min timer for an ecobee thermostat with ventilator attached."""

    _attr_has_entity_name = True
    _attr_name = "Ventilator 20m Timer"

    def __init__(
        self,
        data: EcobeeData,
        thermostat_index: int,
        operating_timezone: tzinfo,
    ) -> None:
        """Initialize ecobee ventilator platform."""
        super().__init__(data, thermostat_index)
        self._attr_unique_id = f"{self.base_unique_id}_ventilator_20m_timer"
        self._attr_is_on = False
        self.update_without_throttle = False
        self._operating_timezone = operating_timezone

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""

        if self.update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            await self.data.update()

        ventilator_off_date_time = self.thermostat["settings"]["ventilatorOffDateTime"]

        self._attr_is_on = ventilator_off_date_time and dt_util.parse_datetime(
            ventilator_off_date_time, raise_on_error=True
        ).replace(tzinfo=self._operating_timezone) >= dt_util.now(
            self._operating_timezone
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


class EcobeeSwitchAuxHeatOnly(EcobeeBaseEntity, SwitchEntity):
    """Representation of a aux_heat_only ecobee switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "aux_heat_only"

    def __init__(
        self,
        data: EcobeeData,
        thermostat_index: int,
    ) -> None:
        """Initialize ecobee ventilator platform."""
        super().__init__(data, thermostat_index)
        self._attr_unique_id = f"{self.base_unique_id}_aux_heat_only"

        self._last_hvac_mode_before_aux_heat = HASS_TO_ECOBEE_HVAC.get(
            HVACMode.HEAT_COOL
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Set the hvacMode to auxHeatOnly."""
        self._last_hvac_mode_before_aux_heat = self.thermostat["settings"]["hvacMode"]
        self.data.ecobee.set_hvac_mode(self.thermostat_index, ECOBEE_AUX_HEAT_ONLY)

    def turn_off(self, **kwargs: Any) -> None:
        """Set the hvacMode back to the prior setting."""
        self.data.ecobee.set_hvac_mode(
            self.thermostat_index, self._last_hvac_mode_before_aux_heat
        )

    @property
    def is_on(self) -> bool:
        """Return true if auxHeatOnly mode is active."""
        return self.thermostat["settings"]["hvacMode"] == ECOBEE_AUX_HEAT_ONLY
