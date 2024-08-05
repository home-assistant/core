"""Support for Climate entities of the Evohome integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

import evohomeasync2 as evo
from evohomeasync2.schema.const import (
    SZ_ACTIVE_FAULTS,
    SZ_SETPOINT_STATUS,
    SZ_SYSTEM_ID,
    SZ_SYSTEM_MODE,
    SZ_SYSTEM_MODE_STATUS,
    SZ_TEMPERATURE_STATUS,
    SZ_UNTIL,
    SZ_ZONE_ID,
    ZoneModelType,
    ZoneType,
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
from homeassistant.const import PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_DURATION_DAYS,
    ATTR_DURATION_HOURS,
    ATTR_DURATION_UNTIL,
    ATTR_SYSTEM_MODE,
    ATTR_ZONE_TEMP,
    DOMAIN,
    EVO_AUTO,
    EVO_AUTOECO,
    EVO_AWAY,
    EVO_CUSTOM,
    EVO_DAYOFF,
    EVO_FOLLOW,
    EVO_HEATOFF,
    EVO_PERMOVER,
    EVO_RESET,
    EVO_TEMPOVER,
    EvoService,
)
from .entity import EvoChild, EvoDevice

if TYPE_CHECKING:
    from . import EvoBroker


_LOGGER = logging.getLogger(__name__)

PRESET_RESET = "Reset"  # reset all child zones to EVO_FOLLOW
PRESET_CUSTOM = "Custom"

HA_HVAC_TO_TCS = {HVACMode.OFF: EVO_HEATOFF, HVACMode.HEAT: EVO_AUTO}

TCS_PRESET_TO_HA = {
    EVO_AWAY: PRESET_AWAY,
    EVO_CUSTOM: PRESET_CUSTOM,
    EVO_AUTOECO: PRESET_ECO,
    EVO_DAYOFF: PRESET_HOME,
    EVO_RESET: PRESET_RESET,
}  # EVO_AUTO: None,

HA_PRESET_TO_TCS = {v: k for k, v in TCS_PRESET_TO_HA.items()}

EVO_PRESET_TO_HA = {
    EVO_FOLLOW: PRESET_NONE,
    EVO_TEMPOVER: "temporary",
    EVO_PERMOVER: "permanent",
}
HA_PRESET_TO_EVO = {v: k for k, v in EVO_PRESET_TO_HA.items()}

STATE_ATTRS_TCS = [SZ_SYSTEM_ID, SZ_ACTIVE_FAULTS, SZ_SYSTEM_MODE_STATUS]
STATE_ATTRS_ZONES = [
    SZ_ZONE_ID,
    SZ_ACTIVE_FAULTS,
    SZ_SETPOINT_STATUS,
    SZ_TEMPERATURE_STATUS,
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the evohome Controller, and its Zones, if any."""
    if discovery_info is None:
        return

    broker: EvoBroker = hass.data[DOMAIN]["broker"]

    _LOGGER.debug(
        "Found the Location/Controller (%s), id=%s, name=%s (location_idx=%s)",
        broker.tcs.modelType,
        broker.tcs.systemId,
        broker.loc.name,
        broker.loc_idx,
    )

    entities: list[EvoClimateEntity] = [EvoController(broker, broker.tcs)]

    for zone in broker.tcs.zones.values():
        if (
            zone.modelType == ZoneModelType.HEATING_ZONE
            or zone.zoneType == ZoneType.THERMOSTAT
        ):
            _LOGGER.debug(
                "Adding: %s (%s), id=%s, name=%s",
                zone.zoneType,
                zone.modelType,
                zone.zoneId,
                zone.name,
            )

            new_entity = EvoZone(broker, zone)
            entities.append(new_entity)

        else:
            _LOGGER.warning(
                (
                    "Ignoring: %s (%s), id=%s, name=%s: unknown/invalid zone type, "
                    "report as an issue if you feel this zone type should be supported"
                ),
                zone.zoneType,
                zone.modelType,
                zone.zoneId,
                zone.name,
            )

    async_add_entities(entities, update_before_add=True)


class EvoClimateEntity(EvoDevice, ClimateEntity):
    """Base for an evohome Climate device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return a list of available hvac operation modes."""
        return list(HA_HVAC_TO_TCS)


class EvoZone(EvoChild, EvoClimateEntity):
    """Base for a Honeywell TCC Zone."""

    _attr_preset_modes = list(HA_PRESET_TO_EVO)

    _evo_device: evo.Zone  # mypy hint

    def __init__(self, evo_broker: EvoBroker, evo_device: evo.Zone) -> None:
        """Initialize a Honeywell TCC Zone."""

        super().__init__(evo_broker, evo_device)
        self._evo_id = evo_device.zoneId

        if evo_device.modelType.startswith("VisionProWifi"):
            # this system does not have a distinct ID for the zone
            self._attr_unique_id = f"{evo_device.zoneId}z"
        else:
            self._attr_unique_id = evo_device.zoneId

        if evo_broker.client_v1:
            self._attr_precision = PRECISION_TENTHS
        else:
            self._attr_precision = self._evo_device.setpointCapabilities[
                "valueResolution"
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
            await self._evo_broker.call_client_api(self._evo_device.reset_mode())
            return

        # otherwise it is EvoService.SET_ZONE_OVERRIDE
        temperature = max(min(data[ATTR_ZONE_TEMP], self.max_temp), self.min_temp)

        if ATTR_DURATION_UNTIL in data:
            duration: timedelta = data[ATTR_DURATION_UNTIL]
            if duration.total_seconds() == 0:
                await self._update_schedule()
                until = dt_util.parse_datetime(self.setpoints.get("next_sp_from", ""))
            else:
                until = dt_util.now() + data[ATTR_DURATION_UNTIL]
        else:
            until = None  # indefinitely

        until = dt_util.as_utc(until) if until else None
        await self._evo_broker.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )

    @property
    def name(self) -> str | None:
        """Return the name of the evohome entity."""
        return self._evo_device.name  # zones can be easily renamed

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current operating mode of a Zone."""
        if self._evo_tcs.system_mode in (EVO_AWAY, EVO_HEATOFF):
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
        if self._evo_tcs.system_mode in (EVO_AWAY, EVO_HEATOFF):
            return TCS_PRESET_TO_HA.get(self._evo_tcs.system_mode)
        if self._evo_device.mode is None:
            return None
        return EVO_PRESET_TO_HA.get(self._evo_device.mode)

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature of a Zone.

        The default is 5, but is user-configurable within 5-21 (in Celsius).
        """
        if self._evo_device.min_heat_setpoint is None:
            return 5
        return self._evo_device.min_heat_setpoint

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature of a Zone.

        The default is 35, but is user-configurable within 21-35 (in Celsius).
        """
        if self._evo_device.max_heat_setpoint is None:
            return 35
        return self._evo_device.max_heat_setpoint

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""

        assert self._evo_device.setpointStatus is not None  # mypy check

        temperature = kwargs["temperature"]

        if (until := kwargs.get("until")) is None:
            if self._evo_device.mode == EVO_FOLLOW:
                await self._update_schedule()
                until = dt_util.parse_datetime(self.setpoints.get("next_sp_from", ""))
            elif self._evo_device.mode == EVO_TEMPOVER:
                until = dt_util.parse_datetime(
                    self._evo_device.setpointStatus[SZ_UNTIL]
                )

        until = dt_util.as_utc(until) if until else None
        await self._evo_broker.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a Zone to one of its native EVO_* operating modes.

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
            await self._evo_broker.call_client_api(
                self._evo_device.set_temperature(self.min_temp, until=None)
            )
        else:  # HVACMode.HEAT
            await self._evo_broker.call_client_api(self._evo_device.reset_mode())

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode; if None, then revert to following the schedule."""
        evo_preset_mode = HA_PRESET_TO_EVO.get(preset_mode, EVO_FOLLOW)

        if evo_preset_mode == EVO_FOLLOW:
            await self._evo_broker.call_client_api(self._evo_device.reset_mode())
            return

        if evo_preset_mode == EVO_TEMPOVER:
            await self._update_schedule()
            until = dt_util.parse_datetime(self.setpoints.get("next_sp_from", ""))
        else:  # EVO_PERMOVER
            until = None

        temperature = self._evo_device.target_heat_temperature
        assert temperature is not None  # mypy check

        until = dt_util.as_utc(until) if until else None
        await self._evo_broker.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )

    async def async_update(self) -> None:
        """Get the latest state data for a Zone."""
        await super().async_update()

        for attr in STATE_ATTRS_ZONES:
            self._device_state_attrs[attr] = getattr(self._evo_device, attr)


class EvoController(EvoClimateEntity):
    """Base for a Honeywell TCC Controller/Location.

    The Controller (aka TCS, temperature control system) is the parent of all the child
    (CH/DHW) devices. It is implemented as a Climate entity to expose the controller's
    operating modes to HA.

    It is assumed there is only one TCS per location, and they are thus synonymous.
    """

    _attr_icon = "mdi:thermostat"
    _attr_precision = PRECISION_TENTHS

    _evo_device: evo.ControlSystem  # mypy hint

    def __init__(self, evo_broker: EvoBroker, evo_device: evo.ControlSystem) -> None:
        """Initialize a Honeywell TCC Controller/Location."""

        super().__init__(evo_broker, evo_device)
        self._evo_id = evo_device.systemId

        self._attr_unique_id = evo_device.systemId
        self._attr_name = evo_device.location.name

        modes = [m[SZ_SYSTEM_MODE] for m in evo_broker.tcs.allowedSystemModes]
        self._attr_preset_modes = [
            TCS_PRESET_TO_HA[m] for m in modes if m in list(TCS_PRESET_TO_HA)
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
            mode = data[ATTR_SYSTEM_MODE]
        else:  # otherwise it is EvoService.RESET_SYSTEM
            mode = EVO_RESET

        if ATTR_DURATION_DAYS in data:
            until = dt_util.start_of_local_day()
            until += data[ATTR_DURATION_DAYS]

        elif ATTR_DURATION_HOURS in data:
            until = dt_util.now() + data[ATTR_DURATION_HOURS]

        else:
            until = None

        await self._set_tcs_mode(mode, until=until)

    async def _set_tcs_mode(self, mode: str, until: datetime | None = None) -> None:
        """Set a Controller to any of its native EVO_* operating modes."""
        until = dt_util.as_utc(until) if until else None
        await self._evo_broker.call_client_api(
            self._evo_tcs.set_mode(mode, until=until)  # type: ignore[arg-type]
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current operating mode of a Controller."""
        tcs_mode = self._evo_tcs.system_mode
        return HVACMode.OFF if tcs_mode == EVO_HEATOFF else HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        """Return the average current temperature of the heating Zones.

        Controllers do not have a current temp, but one is expected by HA.
        """
        temps = [
            z.temperature
            for z in self._evo_tcs.zones.values()
            if z.temperature is not None
        ]
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if not self._evo_tcs.system_mode:
            return None
        return TCS_PRESET_TO_HA.get(self._evo_tcs.system_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Raise exception as Controllers don't have a target temperature."""
        raise NotImplementedError("Evohome Controllers don't have target temperatures.")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set an operating mode for a Controller."""
        if not (tcs_mode := HA_HVAC_TO_TCS.get(hvac_mode)):
            raise HomeAssistantError(f"Invalid hvac_mode: {hvac_mode}")
        await self._set_tcs_mode(tcs_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode; if None, then revert to 'Auto' mode."""
        await self._set_tcs_mode(HA_PRESET_TO_TCS.get(preset_mode, EVO_AUTO))

    async def async_update(self) -> None:
        """Get the latest state data for a Controller."""
        self._device_state_attrs = {}

        attrs = self._device_state_attrs
        for attr in STATE_ATTRS_TCS:
            if attr == SZ_ACTIVE_FAULTS:
                attrs["activeSystemFaults"] = getattr(self._evo_tcs, attr)
            else:
                attrs[attr] = getattr(self._evo_tcs, attr)
