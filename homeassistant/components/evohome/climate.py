"""Support for Climate entities of the Evohome integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import evohomeasync2 as evo
from evohomeasync2.const import (
    SZ_SETPOINT_STATUS,
    SZ_SYSTEM_MODE,
    SZ_SYSTEM_MODE_STATUS,
    SZ_TEMPERATURE_STATUS,
)
from evohomeasync2.schemas.const import (
    SystemMode as EvoSystemMode,
    ZoneMode as EvoZoneMode,
    ZoneModelType as EvoZoneModelType,
    ZoneType as EvoZoneType,
)

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_MODE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import EVOHOME_KEY
from .const import (
    ATTR_DURATION,
    ATTR_DURATION_UNTIL,
    ATTR_PERIOD,
    ATTR_SETPOINT,
    EvoService,
)
from .coordinator import EvoDataUpdateCoordinator
from .entity import EvoChild, EvoEntity

_LOGGER = logging.getLogger(__name__)

PRESET_RESET = "Reset"  # reset all child zones to EvoZoneMode.FOLLOW_SCHEDULE
PRESET_CUSTOM = "Custom"

TCS_PRESET_TO_HA = {
    EvoSystemMode.AWAY: PRESET_AWAY,
    EvoSystemMode.CUSTOM: PRESET_CUSTOM,
    EvoSystemMode.AUTO_WITH_ECO: PRESET_ECO,
    EvoSystemMode.DAY_OFF: PRESET_HOME,
    EvoSystemMode.AUTO_WITH_RESET: PRESET_RESET,
}  # EvoSystemMode.AUTO: None,

HA_PRESET_TO_TCS = {v: k for k, v in TCS_PRESET_TO_HA.items()}

EVO_PRESET_TO_HA = {
    EvoZoneMode.FOLLOW_SCHEDULE: PRESET_NONE,
    EvoZoneMode.TEMPORARY_OVERRIDE: "temporary",
    EvoZoneMode.PERMANENT_OVERRIDE: "permanent",
}
HA_PRESET_TO_EVO = {v: k for k, v in EVO_PRESET_TO_HA.items()}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the evohome Controller, and its Zones, if any."""
    if discovery_info is None:
        return

    coordinator = hass.data[EVOHOME_KEY].coordinator
    loc_idx = hass.data[EVOHOME_KEY].loc_idx
    tcs = hass.data[EVOHOME_KEY].tcs

    _LOGGER.debug(
        "Found the Location/Controller (%s), id=%s, name=%s (location_idx=%s)",
        tcs.model,
        tcs.id,
        tcs.location.name,
        loc_idx,
    )

    entities: list[EvoController | EvoZone] = [EvoController(coordinator, tcs)]

    for zone in tcs.zones:
        if (
            zone.model == EvoZoneModelType.HEATING_ZONE
            or zone.type == EvoZoneType.THERMOSTAT
        ):
            _LOGGER.debug(
                "Adding: %s (%s), id=%s, name=%s",
                zone.type,
                zone.model,
                zone.id,
                zone.name,
            )

            new_entity = EvoZone(coordinator, zone)
            entities.append(new_entity)

        else:
            _LOGGER.warning(
                (
                    "Ignoring: %s (%s), id=%s, name=%s: unknown/invalid zone type, "
                    "report as an issue if you feel this zone type should be supported"
                ),
                zone.type,
                zone.model,
                zone.id,
                zone.name,
            )

    async_add_entities(entities)

    for entity in entities:
        await entity.update_attrs()


class EvoClimateEntity(EvoEntity, ClimateEntity):
    """Base for any evohome-compatible climate entity (controller, zone)."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS


class EvoZone(EvoChild, EvoClimateEntity):
    """Base for any evohome-compatible heating zone."""

    _attr_preset_modes = list(HA_PRESET_TO_EVO)

    _evo_device: evo.Zone
    _evo_id_attr = "zone_id"
    _evo_state_attr_names = (SZ_SETPOINT_STATUS, SZ_TEMPERATURE_STATUS)

    def __init__(
        self, coordinator: EvoDataUpdateCoordinator, evo_device: evo.Zone
    ) -> None:
        """Initialize an evohome-compatible heating zone."""

        super().__init__(coordinator, evo_device)
        self._evo_id = evo_device.id

        if evo_device.model.startswith("VisionProWifi"):
            # this system does not have a distinct ID for the zone
            self._attr_unique_id = f"{evo_device.id}z"
        else:
            self._attr_unique_id = evo_device.id

        if coordinator.client_v1:
            self._attr_precision = PRECISION_TENTHS
        else:
            self._attr_precision = self._evo_device.setpoint_capabilities[
                "value_resolution"
            ]

        self._attr_supported_features = (
            ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

    async def async_zone_svc_request(self, service: str, data: dict[str, Any]) -> None:
        """Process a service request (setpoint override) for a zone."""
        if service == EvoService.RESET_ZONE_OVERRIDE:
            await self.coordinator.call_client_api(self._evo_device.reset())
            return

        # otherwise it is EvoService.SET_ZONE_OVERRIDE
        temperature = max(min(data[ATTR_SETPOINT], self.max_temp), self.min_temp)

        if ATTR_DURATION_UNTIL in data:
            duration: timedelta = data[ATTR_DURATION_UNTIL]
            if duration.total_seconds() == 0:
                await self._update_schedule()
                until = self.setpoints.get("next_sp_from")
            else:
                until = dt_util.now() + data[ATTR_DURATION_UNTIL]
        else:
            until = None  # indefinitely

        until = dt_util.as_utc(until) if until else None
        await self.coordinator.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )

    @property
    def name(self) -> str | None:
        """Return the name of the evohome entity."""
        return self._evo_device.name  # zones can be easily renamed

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current operating mode of a Zone."""
        if self._evo_tcs.mode in (EvoSystemMode.AWAY, EvoSystemMode.HEATING_OFF):
            return HVACMode.AUTO
        if self.target_temperature is None:
            return None
        if self.target_temperature <= self.min_temp:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature of a Zone."""
        return self._evo_device.target_heat_temperature

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._evo_tcs.mode in (EvoSystemMode.AWAY, EvoSystemMode.HEATING_OFF):
            return TCS_PRESET_TO_HA.get(self._evo_tcs.mode)
        return EVO_PRESET_TO_HA.get(self._evo_device.mode)

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature of a Zone.

        The default is 5, but is user-configurable within 5-21 (in Celsius).
        """
        return self._evo_device.min_heat_setpoint

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature of a Zone.

        The default is 35, but is user-configurable within 21-35 (in Celsius).
        """
        return self._evo_device.max_heat_setpoint

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""

        temperature = kwargs["temperature"]

        if (until := kwargs.get("until")) is None:
            if self._evo_device.mode == EvoZoneMode.TEMPORARY_OVERRIDE:
                until = self._evo_device.until
            if self._evo_device.mode == EvoZoneMode.FOLLOW_SCHEDULE:
                await self._update_schedule()
                until = self.setpoints.get("next_sp_from")

        until = dt_util.as_utc(until) if until else None
        await self.coordinator.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a Zone to one of its native operating modes.

        Zones inherit their _effective_ operating mode from their Controller.

        Usually, Zones are in 'FollowSchedule' mode, where their setpoints are a
        function of their own schedule and the Controller's operating mode, e.g.
        'AutoWithEco' mode means their setpoint is (by default) 3C less than scheduled.

        However, Zones can _override_ these setpoints, either indefinitely,
        'PermanentOverride' mode, or for a set period of time, 'TemporaryOverride' mode
        (after which they will revert back to 'FollowSchedule' mode).

        Finally, some of the Controller's operating modes are _forced_ upon the Zones,
        regardless of any override mode, e.g. 'HeatingOff', Zones to (by default) 5C,
        and 'Away', Zones to (by default) 12C.
        """
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.call_client_api(
                self._evo_device.set_temperature(self.min_temp, until=None)
            )
        else:  # HVACMode.HEAT
            await self.coordinator.call_client_api(self._evo_device.reset())

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode; if None, then revert to following the schedule."""
        evo_preset_mode = HA_PRESET_TO_EVO.get(preset_mode, EvoZoneMode.FOLLOW_SCHEDULE)

        if evo_preset_mode == EvoZoneMode.FOLLOW_SCHEDULE:
            await self.coordinator.call_client_api(self._evo_device.reset())
            return

        if evo_preset_mode == EvoZoneMode.TEMPORARY_OVERRIDE:
            await self._update_schedule()
            until = self.setpoints.get("next_sp_from")
        else:  # EvoZoneMode.PERMANENT_OVERRIDE
            until = None

        temperature = self._evo_device.target_heat_temperature
        assert temperature is not None  # mypy check

        until = dt_util.as_utc(until) if until else None
        await self.coordinator.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )


class EvoController(EvoClimateEntity):
    """Base for any evohome-compatible controller.

    The Controller (aka TCS, temperature control system) is the parent of all the child
    (CH/DHW) devices. It is implemented as a Climate entity to expose the controller's
    operating modes to HA.

    It is assumed there is only one TCS per location, and they are thus synonymous.
    """

    _attr_icon = "mdi:thermostat"
    _attr_precision = PRECISION_TENTHS

    _evo_device: evo.ControlSystem
    _evo_id_attr = "system_id"
    _evo_state_attr_names = (SZ_SYSTEM_MODE_STATUS,)

    def __init__(
        self, coordinator: EvoDataUpdateCoordinator, evo_device: evo.ControlSystem
    ) -> None:
        """Initialize an evohome-compatible controller."""

        super().__init__(coordinator, evo_device)
        self._evo_id = evo_device.id

        self._attr_unique_id = evo_device.id
        self._attr_name = evo_device.location.name

        self._evo_modes = [m[SZ_SYSTEM_MODE] for m in evo_device.allowed_system_modes]
        self._attr_preset_modes = [
            TCS_PRESET_TO_HA[m] for m in self._evo_modes if m in list(TCS_PRESET_TO_HA)
        ]
        if self._attr_preset_modes:
            self._attr_supported_features = ClimateEntityFeature.PRESET_MODE
        self._attr_supported_features |= (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        )

    async def async_tcs_svc_request(self, service: str, data: dict[str, Any]) -> None:
        """Process a service request (system mode) for a controller.

        Data validation is not required, it will have been done upstream.
        """
        if service == EvoService.SET_SYSTEM_MODE:
            mode = data[ATTR_MODE]
        else:  # otherwise it is EvoService.RESET_SYSTEM
            mode = EvoSystemMode.AUTO_WITH_RESET

        if ATTR_PERIOD in data:
            until = dt_util.start_of_local_day()
            until += data[ATTR_PERIOD]

        elif ATTR_DURATION in data:
            until = dt_util.now() + data[ATTR_DURATION]

        else:
            until = None

        await self._set_tcs_mode(mode, until=until)

    async def _set_tcs_mode(
        self, mode: EvoSystemMode, until: datetime | None = None
    ) -> None:
        """Set a Controller to any of its native operating modes."""
        until = dt_util.as_utc(until) if until else None
        await self.coordinator.call_client_api(
            self._evo_device.set_mode(mode, until=until)
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current operating mode of a Controller."""
        evo_mode = self._evo_device.mode
        return (
            HVACMode.OFF
            if evo_mode in (EvoSystemMode.HEATING_OFF, EvoSystemMode.OFF)
            else HVACMode.HEAT
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the average current temperature of the heating Zones.

        Controllers do not have a current temp, but one is expected by HA.
        """
        temps = [
            z.temperature for z in self._evo_device.zones if z.temperature is not None
        ]
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return TCS_PRESET_TO_HA.get(self._evo_device.mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Raise exception as Controllers don't have a target temperature."""
        raise NotImplementedError("Evohome Controllers don't have target temperatures.")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set an operating mode for a Controller."""

        evo_mode: EvoSystemMode

        if hvac_mode == HVACMode.HEAT:
            evo_mode = (
                EvoSystemMode.AUTO
                if EvoSystemMode.AUTO in self._evo_modes
                else EvoSystemMode.HEAT
            )
        elif hvac_mode == HVACMode.OFF:
            evo_mode = (
                EvoSystemMode.HEATING_OFF
                if EvoSystemMode.HEATING_OFF in self._evo_modes
                else EvoSystemMode.OFF
            )
        else:
            raise HomeAssistantError(f"Invalid hvac_mode: {hvac_mode}")
        await self._set_tcs_mode(evo_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode; if None, then revert to 'Auto' mode."""
        await self._set_tcs_mode(HA_PRESET_TO_TCS.get(preset_mode, EvoSystemMode.AUTO))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._device_state_attrs = {
            "activeSystemFaults": self._evo_device.active_faults
            + self._evo_device.gateway.active_faults
        }

        super()._handle_coordinator_update()

    async def update_attrs(self) -> None:
        """Update the entity's extra state attrs."""
        self._handle_coordinator_update()
