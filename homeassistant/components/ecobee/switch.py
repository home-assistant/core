"""Support for using switch with ecobee thermostats."""

from dataclasses import dataclass
from datetime import tzinfo
import logging
from typing import Any, Self, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from . import EcobeeConfigEntry, EcobeeData
from .const import ECOBEE_AUX_HEAT_ONLY, ECOBEE_HVAC_MODES
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
    """Represent 20 min timer for an ecobee thermostat with ventilator."""

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

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set ventilator 20 min timer on."""
        await self.hass.async_add_executor_job(
            self.data.ecobee.set_ventilator_timer, self.thermostat_index, True
        )
        self.update_without_throttle = True

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set ventilator 20 min timer off."""
        await self.hass.async_add_executor_job(
            self.data.ecobee.set_ventilator_timer, self.thermostat_index, False
        )
        self.update_without_throttle = True


@dataclass
class EcobeeAuxHeatOnlyExtraStoredData(ExtraStoredData):
    """Object to hold the HVAC mode to restore after auxiliary heat."""

    hvac_mode: str

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {"hvac_mode_before_aux_heat": self.hvac_mode}

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize restored auxiliary heat data."""
        if not isinstance(hvac_mode := restored.get("hvac_mode_before_aux_heat"), str):
            return None
        if hvac_mode not in ECOBEE_HVAC_MODES:
            return None
        return cls(hvac_mode)


class EcobeeSwitchAuxHeatOnly(EcobeeBaseEntity, SwitchEntity, RestoreEntity):
    """Representation of a aux_heat_only ecobee switch."""

    _attr_translation_key = "aux_heat_only"

    def __init__(
        self,
        data: EcobeeData,
        thermostat_index: int,
    ) -> None:
        """Initialize ecobee ventilator platform."""
        super().__init__(data, thermostat_index)
        self._attr_unique_id = f"{self.base_unique_id}_aux_heat_only"

        self._last_hvac_mode_before_aux_heat: str | None = None
        self.update_without_throttle = False

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the previous HVAC mode when auxiliary heat was active."""
        await super().async_added_to_hass()
        if not self.is_on:
            return
        if not (extra_data := await self.async_get_last_extra_data()):
            _LOGGER.warning(
                "Auxiliary heat is active but no previous HVAC mode was saved"
            )
            return
        if (
            hvac_mode := EcobeeAuxHeatOnlyExtraStoredData.from_dict(
                extra_data.as_dict()
            )
        ) is not None:
            self._last_hvac_mode_before_aux_heat = hvac_mode.hvac_mode
        else:
            _LOGGER.warning(
                "Auxiliary heat is active but no valid previous HVAC mode was saved"
            )

    @property
    @override
    def extra_restore_state_data(self) -> EcobeeAuxHeatOnlyExtraStoredData | None:
        """Return the HVAC mode to restore after auxiliary heat."""
        if self._last_hvac_mode_before_aux_heat is None:
            return None
        return EcobeeAuxHeatOnlyExtraStoredData(self._last_hvac_mode_before_aux_heat)

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Set the hvacMode to auxHeatOnly."""
        if self.is_on:
            return
        hvac_mode = self.thermostat["settings"]["hvacMode"]
        self._last_hvac_mode_before_aux_heat = hvac_mode
        self.data.ecobee.set_hvac_mode(self.thermostat_index, ECOBEE_AUX_HEAT_ONLY)
        self.update_without_throttle = True

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Set the hvacMode back to the prior setting."""
        if not self.is_on:
            return
        hvac_mode = self._last_hvac_mode_before_aux_heat
        if hvac_mode is None:
            hvac_mode = "auto"
            _LOGGER.warning(
                "No previous HVAC mode saved for %s; falling back to %s",
                self.entity_id,
                hvac_mode,
            )
        self.data.ecobee.set_hvac_mode(self.thermostat_index, hvac_mode)
        self.update_without_throttle = True

    async def async_update(self) -> None:
        """Update the switch state from the thermostat."""
        update_without_throttle = self.update_without_throttle
        if update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            await self.data.update()
        if not self.is_on and not update_without_throttle:
            self._last_hvac_mode_before_aux_heat = None

    @property
    @override
    def is_on(self) -> bool:
        """Return true if auxHeatOnly mode is active."""
        return self.thermostat["settings"]["hvacMode"] == ECOBEE_AUX_HEAT_ONLY
