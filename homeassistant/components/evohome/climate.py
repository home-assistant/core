"""Support for Climate devices of (EMEA/EU-based) Honeywell TCC systems."""
import logging
from typing import List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
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
from homeassistant.util.dt import parse_datetime

from . import CONF_LOCATION_IDX, EvoChild, EvoDevice
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

    # special case of RoundModulation/RoundWireless as a single zone system
    if len(broker.tcs.zones) == 1 and list(broker.tcs.zones.keys())[0] == "Thermostat":
        zone = list(broker.tcs.zones.values())[0]
        _LOGGER.debug(
            "Found the Thermostat (%s), id=%s, name=%s",
            zone.modelType,
            zone.zoneId,
            zone.name,
        )

        async_add_entities([EvoThermostat(broker, zone)], update_before_add=True)
        return

    controller = EvoController(broker, broker.tcs)

    zones = []
    for zone in broker.tcs.zones.values():
        _LOGGER.debug(
            "Found a %s (%s), id=%s, name=%s",
            zone.zoneType,
            zone.modelType,
            zone.zoneId,
            zone.name,
        )
        zones.append(EvoZone(broker, zone))

    async_add_entities([controller] + zones, update_before_add=True)


class EvoClimateDevice(EvoDevice, ClimateDevice):
    """Base for a Honeywell evohome Climate device."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize a Climate device."""
        super().__init__(evo_broker, evo_device)

        self._preset_modes = None

    async def _set_tcs_mode(self, op_mode: str) -> None:
        """Set a Controller to any of its native EVO_* operating modes."""
        await self._call_client_api(self._evo_tcs.set_status(op_mode))

    @property
    def hvac_modes(self) -> List[str]:
        """Return a list of available hvac operation modes."""
        return list(HA_HVAC_TO_TCS)

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return self._preset_modes


class EvoZone(EvoChild, EvoClimateDevice):
    """Base for a Honeywell evohome Zone."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize a Zone."""
        super().__init__(evo_broker, evo_device)

        self._unique_id = evo_device.zoneId
        self._name = evo_device.name
        self._icon = "mdi:radiator"

        self._supported_features = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE
        self._preset_modes = list(HA_PRESET_TO_EVO)
        if evo_broker.client_v1:
            self._precision = PRECISION_TENTHS
        else:
            self._precision = self._evo_device.setpointCapabilities["valueResolution"]

    @property
    def hvac_mode(self) -> str:
        """Return the current operating mode of a Zone."""
        if self._evo_tcs.systemModeStatus["mode"] in [EVO_AWAY, EVO_HEATOFF]:
            return HVAC_MODE_AUTO
        is_off = self.target_temperature <= self.min_temp
        return HVAC_MODE_OFF if is_off else HVAC_MODE_HEAT

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported."""
        if self._evo_tcs.systemModeStatus["mode"] == EVO_HEATOFF:
            return CURRENT_HVAC_OFF
        if self.target_temperature <= self.min_temp:
            return CURRENT_HVAC_OFF
        if not self._evo_device.temperatureStatus["isAvailable"]:
            return None
        if self.target_temperature <= self.current_temperature:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_HEAT

    @property
    def target_temperature(self) -> float:
        """Return the target temperature of a Zone."""
        return self._evo_device.setpointStatus["targetHeatTemperature"]

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._evo_tcs.systemModeStatus["mode"] in [EVO_AWAY, EVO_HEATOFF]:
            return TCS_PRESET_TO_HA.get(self._evo_tcs.systemModeStatus["mode"])
        return EVO_PRESET_TO_HA.get(
            self._evo_device.setpointStatus["setpointMode"], "follow"
        )

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

        if self._evo_device.setpointStatus["setpointMode"] == EVO_FOLLOW:
            await self._update_schedule()
            until = parse_datetime(str(self.setpoints.get("next_sp_from")))
        elif self._evo_device.setpointStatus["setpointMode"] == EVO_TEMPOVER:
            until = parse_datetime(self._evo_device.setpointStatus["until"])
        else:  # EVO_PERMOVER
            until = None

        await self._call_client_api(
            self._evo_device.set_temperature(temperature, until)
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
            await self._call_client_api(
                self._evo_device.set_temperature(self.min_temp, until=None)
            )
        else:  # HVAC_MODE_HEAT
            await self._call_client_api(self._evo_device.cancel_temp_override())

    async def async_set_preset_mode(self, preset_mode: Optional[str]) -> None:
        """Set the preset mode; if None, then revert to following the schedule."""
        evo_preset_mode = HA_PRESET_TO_EVO.get(preset_mode, EVO_FOLLOW)

        if evo_preset_mode == EVO_FOLLOW:
            await self._call_client_api(self._evo_device.cancel_temp_override())
            return

        temperature = self._evo_device.setpointStatus["targetHeatTemperature"]

        if evo_preset_mode == EVO_TEMPOVER:
            await self._update_schedule()
            until = parse_datetime(str(self.setpoints.get("next_sp_from")))
        else:  # EVO_PERMOVER
            until = None

        await self._call_client_api(
            self._evo_device.set_temperature(temperature, until)
        )

    async def async_update(self) -> None:
        """Get the latest state data for a Zone."""
        await super().async_update()

        for attr in STATE_ATTRS_ZONES:
            self._device_state_attrs[attr] = getattr(self._evo_device, attr)


class EvoController(EvoClimateDevice):
    """Base for a Honeywell evohome Controller (hub).

    The Controller (aka TCS, temperature control system) is the parent of all
    the child (CH/DHW) devices.  It is also a Climate device.
    """

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize a evohome Controller (hub)."""
        super().__init__(evo_broker, evo_device)

        self._unique_id = evo_device.systemId
        self._name = evo_device.location.name
        self._icon = "mdi:thermostat"

        self._precision = PRECISION_TENTHS
        self._supported_features = SUPPORT_PRESET_MODE
        self._preset_modes = list(HA_PRESET_TO_TCS)

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


class EvoThermostat(EvoZone):
    """Base for a Honeywell Round Thermostat.

    These are implemented as a combined Controller/Zone.
    """

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the Thermostat."""
        super().__init__(evo_broker, evo_device)

        self._name = evo_broker.tcs.location.name
        self._preset_modes = [PRESET_AWAY, PRESET_ECO]

    @property
    def hvac_mode(self) -> str:
        """Return the current operating mode."""
        if self._evo_tcs.systemModeStatus["mode"] == EVO_HEATOFF:
            return HVAC_MODE_OFF

        return super().hvac_mode

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        if (
            self._evo_tcs.systemModeStatus["mode"] == EVO_AUTOECO
            and self._evo_device.setpointStatus["setpointMode"] == EVO_FOLLOW
        ):
            return PRESET_ECO

        return super().preset_mode

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set an operating mode."""
        await self._set_tcs_mode(HA_HVAC_TO_TCS.get(hvac_mode))

    async def async_set_preset_mode(self, preset_mode: Optional[str]) -> None:
        """Set the preset mode; if None, then revert to following the schedule."""
        if preset_mode in list(HA_PRESET_TO_TCS):
            await self._set_tcs_mode(HA_PRESET_TO_TCS.get(preset_mode))
        else:
            await super().async_set_hvac_mode(preset_mode)

    async def async_update(self) -> None:
        """Get the latest state data for the Thermostat."""
        await super().async_update()

        attrs = self._device_state_attrs
        for attr in STATE_ATTRS_TCS:
            if attr == "activeFaults":  # self._evo_device also has "activeFaults"
                attrs["activeSystemFaults"] = getattr(self._evo_tcs, attr)
            else:
                attrs[attr] = getattr(self._evo_tcs, attr)
