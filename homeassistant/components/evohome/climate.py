"""Support for Climate devices of (EMEA/EU-based) Honeywell TCC systems."""
from datetime import datetime as dt
import logging
from typing import List, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import PRECISION_TENTHS
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.util.dt as dt_util

from . import (
    ATTR_DURATION_DAYS,
    ATTR_DURATION_HOURS,
    ATTR_DURATION_UNTIL,
    ATTR_SYSTEM_MODE,
    ATTR_ZONE_TEMP,
    CONF_LOCATION_IDX,
    SVC_RESET_ZONE_OVERRIDE,
    SVC_SET_SYSTEM_MODE,
    EvoChild,
    EvoDevice,
)
from .const import (
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
)

_LOGGER = logging.getLogger(__name__)

PRESET_RESET = "Reset"  # reset all child zones to EVO_FOLLOW
PRESET_CUSTOM = "Custom"

HA_HVAC_TO_TCS = {HVAC_MODE_OFF: EVO_HEATOFF, HVAC_MODE_HEAT: EVO_AUTO}

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

STATE_ATTRS_TCS = ["systemId", "activeFaults", "systemModeStatus"]
STATE_ATTRS_ZONES = ["zoneId", "activeFaults", "setpointStatus", "temperatureStatus"]


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    """Create the evohome Controller, and its Zones, if any."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    _LOGGER.debug(
        "Found the Location/Controller (%s), id=%s, name=%s (location_idx=%s)",
        broker.tcs.modelType,
        broker.tcs.systemId,
        broker.tcs.location.name,
        broker.params[CONF_LOCATION_IDX],
    )

    controller = EvoController(broker, broker.tcs)

    zones = []
    for zone in broker.tcs.zones.values():
        if zone.modelType == "HeatingZone" or zone.zoneType == "Thermostat":
            _LOGGER.debug(
                "Adding: %s (%s), id=%s, name=%s",
                zone.zoneType,
                zone.modelType,
                zone.zoneId,
                zone.name,
            )

            new_entity = EvoZone(broker, zone)
            zones.append(new_entity)

        else:
            _LOGGER.warning(
                "Ignoring: %s (%s), id=%s, name=%s: unknown/invalid zone type, "
                "report as an issue if you feel this zone type should be supported",
                zone.zoneType,
                zone.modelType,
                zone.zoneId,
                zone.name,
            )

    async_add_entities([controller] + zones, update_before_add=True)


class EvoClimateEntity(EvoDevice, ClimateEntity):
    """Base for an evohome Climate device."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize a Climate device."""
        super().__init__(evo_broker, evo_device)

        self._preset_modes = None

    @property
    def hvac_modes(self) -> List[str]:
        """Return a list of available hvac operation modes."""
        return list(HA_HVAC_TO_TCS)

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return self._preset_modes


class EvoZone(EvoChild, EvoClimateEntity):
    """Base for a Honeywell TCC Zone."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize a Honeywell TCC Zone."""
        super().__init__(evo_broker, evo_device)

        if evo_device.modelType.startswith("VisionProWifi"):
            # this system does not have a distinct ID for the zone
            self._unique_id = f"{evo_device.zoneId}z"
        else:
            self._unique_id = evo_device.zoneId

        self._name = evo_device.name
        self._icon = "mdi:radiator"

        if evo_broker.client_v1:
            self._precision = PRECISION_TENTHS
        else:
            self._precision = self._evo_device.setpointCapabilities["valueResolution"]

        self._preset_modes = list(HA_PRESET_TO_EVO)
        self._supported_features = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE

    async def async_zone_svc_request(self, service: dict, data: dict) -> None:
        """Process a service request (setpoint override) for a zone."""
        if service == SVC_RESET_ZONE_OVERRIDE:
            await self._evo_broker.call_client_api(
                self._evo_device.cancel_temp_override()
            )
            return

        # otherwise it is SVC_SET_ZONE_OVERRIDE
        temperature = max(min(data[ATTR_ZONE_TEMP], self.max_temp), self.min_temp)

        if ATTR_DURATION_UNTIL in data:
            duration = data[ATTR_DURATION_UNTIL]
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
    def hvac_mode(self) -> str:
        """Return the current operating mode of a Zone."""
        if self._evo_tcs.systemModeStatus["mode"] in [EVO_AWAY, EVO_HEATOFF]:
            return HVAC_MODE_AUTO
        is_off = self.target_temperature <= self.min_temp
        return HVAC_MODE_OFF if is_off else HVAC_MODE_HEAT

    @property
    def target_temperature(self) -> float:
        """Return the target temperature of a Zone."""
        return self._evo_device.setpointStatus["targetHeatTemperature"]

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._evo_tcs.systemModeStatus["mode"] in [EVO_AWAY, EVO_HEATOFF]:
            return TCS_PRESET_TO_HA.get(self._evo_tcs.systemModeStatus["mode"])
        return EVO_PRESET_TO_HA.get(self._evo_device.setpointStatus["setpointMode"])

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature of a Zone.

        The default is 5, but is user-configurable within 5-35 (in Celsius).
        """
        return self._evo_device.setpointCapabilities["minHeatSetpoint"]

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature of a Zone.

        The default is 35, but is user-configurable within 5-35 (in Celsius).
        """
        return self._evo_device.setpointCapabilities["maxHeatSetpoint"]

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperature."""
        temperature = kwargs["temperature"]
        until = kwargs.get("until")

        if until is None:
            if self._evo_device.setpointStatus["setpointMode"] == EVO_FOLLOW:
                await self._update_schedule()
                until = dt_util.parse_datetime(self.setpoints.get("next_sp_from", ""))
            elif self._evo_device.setpointStatus["setpointMode"] == EVO_TEMPOVER:
                until = dt_util.parse_datetime(self._evo_device.setpointStatus["until"])

        until = dt_util.as_utc(until) if until else None
        await self._evo_broker.call_client_api(
            self._evo_device.set_temperature(temperature, until=until)
        )

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
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
        if hvac_mode == HVAC_MODE_OFF:
            await self._evo_broker.call_client_api(
                self._evo_device.set_temperature(self.min_temp, until=None)
            )
        else:  # HVAC_MODE_HEAT
            await self._evo_broker.call_client_api(
                self._evo_device.cancel_temp_override()
            )

    async def async_set_preset_mode(self, preset_mode: Optional[str]) -> None:
        """Set the preset mode; if None, then revert to following the schedule."""
        evo_preset_mode = HA_PRESET_TO_EVO.get(preset_mode, EVO_FOLLOW)

        if evo_preset_mode == EVO_FOLLOW:
            await self._evo_broker.call_client_api(
                self._evo_device.cancel_temp_override()
            )
            return

        temperature = self._evo_device.setpointStatus["targetHeatTemperature"]

        if evo_preset_mode == EVO_TEMPOVER:
            await self._update_schedule()
            until = dt_util.parse_datetime(self.setpoints.get("next_sp_from", ""))
        else:  # EVO_PERMOVER
            until = None

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

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize a Honeywell TCC Controller/Location."""
        super().__init__(evo_broker, evo_device)

        self._unique_id = evo_device.systemId
        self._name = evo_device.location.name
        self._icon = "mdi:thermostat"

        self._precision = PRECISION_TENTHS

        modes = [m["systemMode"] for m in evo_broker.config["allowedSystemModes"]]
        self._preset_modes = [
            TCS_PRESET_TO_HA[m] for m in modes if m in list(TCS_PRESET_TO_HA)
        ]
        self._supported_features = SUPPORT_PRESET_MODE if self._preset_modes else 0

    async def async_tcs_svc_request(self, service: dict, data: dict) -> None:
        """Process a service request (system mode) for a controller.

        Data validation is not required, it will have been done upstream.
        """
        if service == SVC_SET_SYSTEM_MODE:
            mode = data[ATTR_SYSTEM_MODE]
        else:  # otherwise it is SVC_RESET_SYSTEM
            mode = EVO_RESET

        if ATTR_DURATION_DAYS in data:
            until = dt_util.start_of_local_day()
            until += data[ATTR_DURATION_DAYS]

        elif ATTR_DURATION_HOURS in data:
            until = dt_util.now() + data[ATTR_DURATION_HOURS]

        else:
            until = None

        await self._set_tcs_mode(mode, until=until)

    async def _set_tcs_mode(self, mode: str, until: Optional[dt] = None) -> None:
        """Set a Controller to any of its native EVO_* operating modes."""
        until = dt_util.as_utc(until) if until else None
        await self._evo_broker.call_client_api(
            self._evo_tcs.set_status(mode, until=until)
        )

    @property
    def hvac_mode(self) -> str:
        """Return the current operating mode of a Controller."""
        tcs_mode = self._evo_tcs.systemModeStatus["mode"]
        return HVAC_MODE_OFF if tcs_mode == EVO_HEATOFF else HVAC_MODE_HEAT

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the average current temperature of the heating Zones.

        Controllers do not have a current temp, but one is expected by HA.
        """
        temps = [
            z.temperatureStatus["temperature"]
            for z in self._evo_tcs.zones.values()
            if z.temperatureStatus["isAvailable"]
        ]
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return TCS_PRESET_TO_HA.get(self._evo_tcs.systemModeStatus["mode"])

    @property
    def min_temp(self) -> float:
        """Return None as Controllers don't have a target temperature."""
        return None

    @property
    def max_temp(self) -> float:
        """Return None as Controllers don't have a target temperature."""
        return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Raise exception as Controllers don't have a target temperature."""
        raise NotImplementedError("Evohome Controllers don't have target temperatures.")

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set an operating mode for a Controller."""
        await self._set_tcs_mode(HA_HVAC_TO_TCS.get(hvac_mode))

    async def async_set_preset_mode(self, preset_mode: Optional[str]) -> None:
        """Set the preset mode; if None, then revert to 'Auto' mode."""
        await self._set_tcs_mode(HA_PRESET_TO_TCS.get(preset_mode, EVO_AUTO))

    async def async_update(self) -> None:
        """Get the latest state data for a Controller."""
        self._device_state_attrs = {}

        attrs = self._device_state_attrs
        for attr in STATE_ATTRS_TCS:
            if attr == "activeFaults":
                attrs["activeSystemFaults"] = getattr(self._evo_tcs, attr)
            else:
                attrs[attr] = getattr(self._evo_tcs, attr)
