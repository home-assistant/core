"""Support for Climate entities of the Evohome integration."""

from datetime import datetime, timedelta
import logging
from typing import Any, override

import evohomeasync2 as evo
from evohomeasync2.const import (
    SZ_CAN_BE_TEMPORARY,
    SZ_DURATION,
    SZ_MODE,
    SZ_PERIOD,
    SZ_SETPOINT_STATUS,
    SZ_SYSTEM_MODE,
    SZ_SYSTEM_MODE_STATUS,
    SZ_TEMPERATURE_STATUS,
    SZ_TIMING_MODE,
    SZ_UNTIL,
    SystemMode as EvoSystemMode,
    ZoneMode as EvoZoneMode,
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
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVOHOME_DATA, NEXT_SP_FROM, EvoService
from .coordinator import EvoDataUpdateCoordinator
from .entity import EvoChild, EvoEntity, is_valid_zone, unique_zone_id
from .helpers import as_snake_case

_LOGGER = logging.getLogger(__name__)

PRESET_CUSTOM = "Custom"

TCS_PRESET_TO_HA = {
    EvoSystemMode.AWAY: PRESET_AWAY,
    EvoSystemMode.CUSTOM: PRESET_CUSTOM,
    EvoSystemMode.AUTO_WITH_ECO: PRESET_ECO,
    EvoSystemMode.DAY_OFF: PRESET_HOME,
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
    _: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the climate platform for Evohome."""

    if discovery_info is None:
        return

    coordinator = hass.data[EVOHOME_DATA].coordinator
    tcs = hass.data[EVOHOME_DATA].tcs

    _LOGGER.debug(
        "Found the Location/Controller (%s), id=%s, name=%s (location_idx=%s)",
        tcs.model,
        tcs.id,
        tcs.location.name,
        coordinator.loc_idx,
    )

    entities: list[EvoController | EvoZone] = [EvoController(coordinator, tcs)]

    for zone in tcs.zones:
        if is_valid_zone(zone):
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
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    async def async_set_system_mode(
        self,
        mode: str,
        duration: timedelta | None = None,
        period: timedelta | None = None,
    ) -> None:
        """Set the system mode; only supported by controllers."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="controller_only_service",
            translation_placeholders={"service": EvoService.SET_SYSTEM_MODE},
        )

    async def async_set_zone_override(
        self, setpoint: float, duration: timedelta | None = None
    ) -> None:
        """Set the zone override; only supported by zones."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="zone_only_service",
            translation_placeholders={"service": EvoService.SET_ZONE_OVERRIDE},
        )


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

        self._attr_unique_id = unique_zone_id(evo_device)

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

    @override
    async def async_set_zone_override(
        self, setpoint: float, duration: timedelta | None = None
    ) -> None:
        """Override the zone's setpoint, either permanently or for a duration."""
        temperature = max(min(setpoint, self.max_temp), self.min_temp)

        if duration is None:
            until = None  # indefinitely
        elif duration.total_seconds() == 0:
            await self.coordinator.async_ensure_schedule(self._evo_device)
            until = self.setpoints.get(NEXT_SP_FROM)
        else:
            until = dt_util.now() + duration

        until = dt_util.as_utc(until) if until else None

        await self.coordinator.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )

    @property
    @override
    def name(self) -> str:
        """Return the name of the evohome entity."""
        return self._evo_device.name  # zones can be renamed

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the current operating mode of a Zone."""
        if self._evo_tcs.mode in (EvoSystemMode.AWAY, EvoSystemMode.HEATING_OFF):
            return HVACMode.AUTO
        if self.native_target_temperature is None:
            return None
        if self.native_target_temperature <= self.min_temp:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the target temperature of a Zone."""
        return self._evo_device.target_heat_temperature

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._evo_tcs.mode in (EvoSystemMode.AWAY, EvoSystemMode.HEATING_OFF):
            return TCS_PRESET_TO_HA.get(self._evo_tcs.mode)
        return EVO_PRESET_TO_HA.get(self._evo_device.mode)

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum target temperature of a Zone.

        The default is 5, but is user-configurable within 5-21 (in Celsius).
        """
        return self._evo_device.min_heat_setpoint

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum target temperature of a Zone.

        The default is 35, but is user-configurable within 21-35 (in Celsius).
        """
        return self._evo_device.max_heat_setpoint

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""

        temperature = kwargs[ATTR_TEMPERATURE]

        if (until := kwargs.get(SZ_UNTIL)) is None:
            if self._evo_device.mode == EvoZoneMode.TEMPORARY_OVERRIDE:
                until = self._evo_device.until
            if self._evo_device.mode == EvoZoneMode.FOLLOW_SCHEDULE:
                await self.coordinator.async_ensure_schedule(self._evo_device)
                until = self.setpoints.get(NEXT_SP_FROM)

        until = dt_util.as_utc(until) if until else None
        await self.coordinator.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )

    @override
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

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode; if None, then revert to following the schedule."""
        evo_preset_mode = HA_PRESET_TO_EVO.get(preset_mode, EvoZoneMode.FOLLOW_SCHEDULE)

        if evo_preset_mode == EvoZoneMode.FOLLOW_SCHEDULE:
            await self.coordinator.call_client_api(self._evo_device.reset())
            return

        if evo_preset_mode == EvoZoneMode.TEMPORARY_OVERRIDE:
            await self.coordinator.async_ensure_schedule(self._evo_device)
            until = self.setpoints.get(NEXT_SP_FROM)
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

    _attr_icon = "mdi:thermostat-box"
    _attr_precision = PRECISION_TENTHS

    _evo_device: evo.ControlSystem
    _evo_id_attr = "system_id"
    _evo_state_attr_names = (SZ_SYSTEM_MODE_STATUS,)

    def __init__(
        self, coordinator: EvoDataUpdateCoordinator, evo_device: evo.ControlSystem
    ) -> None:
        """Initialize an evohome-compatible controller."""

        super().__init__(coordinator, evo_device)

        self._attr_unique_id = evo_device.id
        self._attr_name = evo_device.location.name

        self._evo_modes = {
            m[SZ_SYSTEM_MODE].value: m for m in evo_device.allowed_system_modes
        }
        self._attr_preset_modes = [
            TCS_PRESET_TO_HA[mode]
            for m in evo_device.allowed_system_modes
            if (mode := m[SZ_SYSTEM_MODE]) in TCS_PRESET_TO_HA
        ]
        if self._attr_preset_modes:
            self._attr_supported_features = ClimateEntityFeature.PRESET_MODE
        self._attr_supported_features |= (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        )

    @override
    async def async_set_system_mode(
        self,
        mode: str,
        duration: timedelta | None = None,
        period: timedelta | None = None,
    ) -> None:
        """Set the system mode, either indefinitely or for a duration/period."""

        # check the requested mode; not all systems support all modes...
        if (mode_info := self._evo_modes.get(as_snake_case(mode))) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mode_not_supported",
                translation_placeholders={SZ_MODE: mode},
            )

        timing_mode: str | None = None
        until: datetime | None = None

        # service schema makes duration & period mutually exclusive (can be neither)
        if period is not None:
            timing_mode, until = SZ_PERIOD, dt_util.start_of_local_day() + period
        elif duration is not None:
            timing_mode, until = SZ_DURATION, dt_util.now() + duration

        if timing_mode is not None:
            if not mode_info[SZ_CAN_BE_TEMPORARY]:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="mode_cant_be_temporary",
                    translation_placeholders={SZ_MODE: mode},
                )
            if mode_info.get(SZ_TIMING_MODE) != timing_mode:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key=f"mode_cant_have_{timing_mode}",
                    translation_placeholders={SZ_MODE: mode},
                )

        await self._set_tcs_mode(mode_info[SZ_SYSTEM_MODE], until=until)

    async def _set_tcs_mode(
        self, mode: EvoSystemMode, until: datetime | None = None
    ) -> None:
        """Set a Controller to any of its native operating modes."""
        until = dt_util.as_utc(until) if until else None
        try:
            await self.coordinator.call_client_api(
                self._evo_device.set_mode(mode, until=until)
            )
        except evo.InvalidModeRequestError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_system_mode",
                translation_placeholders={"error": str(err)},
            ) from err

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the current operating mode of a Controller."""
        evo_mode = self._evo_device.mode
        return (
            HVACMode.OFF
            if evo_mode in (EvoSystemMode.HEATING_OFF, EvoSystemMode.OFF)
            else HVACMode.HEAT
        )

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the average current temperature of the heating Zones.

        Controllers do not have a current temp, but one is expected by HA.
        """
        temps = [
            z.temperature for z in self._evo_device.zones if z.temperature is not None
        ]
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return TCS_PRESET_TO_HA.get(self._evo_device.mode)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Raise exception as Controllers don't have a target temperature."""
        raise NotImplementedError("Evohome Controllers don't have target temperatures.")

    @override
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

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode; if None, then revert to 'Auto' mode."""
        await self._set_tcs_mode(HA_PRESET_TO_TCS.get(preset_mode, EvoSystemMode.AUTO))

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._device_state_attrs = {
            "activeSystemFaults": self._evo_device.active_faults
            + self._evo_device.gateway.active_faults
        }

        super()._handle_coordinator_update()

    @override
    async def update_attrs(self) -> None:
        """Update the entity's extra state attrs."""
        self._handle_coordinator_update()
