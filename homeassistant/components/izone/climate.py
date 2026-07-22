"""Support for the iZone HVAC."""

from collections.abc import Callable, Mapping
import logging
from typing import Any, Concatenate, override

from pizone import Controller, Zone
import voluptuous as vol

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_TOP,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import VolDictType

from .const import (
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_ZONE_UPDATE,
    DOMAIN,
    TIMEOUT_DISCOVERY,
)

type _FuncType[_T, **_P, _R] = Callable[Concatenate[_T, _P], _R]

_LOGGER = logging.getLogger(__name__)

_IZONE_FAN_TO_HA = {
    Controller.Fan.LOW: FAN_LOW,
    Controller.Fan.MED: FAN_MEDIUM,
    Controller.Fan.HIGH: FAN_HIGH,
    Controller.Fan.TOP: FAN_TOP,
    Controller.Fan.AUTO: FAN_AUTO,
}

ATTR_AIRFLOW = "airflow"

IZONE_SERVICE_AIRFLOW_MIN = "airflow_min"
IZONE_SERVICE_AIRFLOW_MAX = "airflow_max"

IZONE_SERVICE_AIRFLOW_SCHEMA: VolDictType = {
    vol.Required(ATTR_AIRFLOW): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100), msg="invalid airflow"
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize an IZone Controller."""
    disco = hass.data[DATA_DISCOVERY_SERVICE]
    entry_unique_id = config.unique_id
    initialized = False

    @callback
    def init_controller(ctrl: Controller):
        """Register the controller device and the containing zones."""
        nonlocal initialized
        if entry_unique_id and ctrl.device_uid != entry_unique_id:
            return
        if initialized:
            return

        initialized = True
        device = ControllerDevice(ctrl)
        async_add_entities([device])
        async_add_entities(device.zones.values())
        _LOGGER.debug("Controller UID=%s initialized", ctrl.device_uid)

    # Fetch the controller for this entry, waiting for discovery if it hasn't been found yet
    if ctrl := await disco.pi_disco.fetch_controller(
        entry_unique_id, timeout=TIMEOUT_DISCOVERY
    ):
        init_controller(ctrl)

    # connect to register any further components
    config.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_CONTROLLER_DISCOVERED, init_controller)
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        IZONE_SERVICE_AIRFLOW_MIN,
        IZONE_SERVICE_AIRFLOW_SCHEMA,
        "async_set_airflow_min",
    )
    platform.async_register_entity_service(
        IZONE_SERVICE_AIRFLOW_MAX,
        IZONE_SERVICE_AIRFLOW_SCHEMA,
        "async_set_airflow_max",
    )


def _return_on_connection_error[_DeviceT: ControllerDevice | ZoneDevice, **_P, _R, _T](
    ret: _T = None,  # type: ignore[assignment]
) -> Callable[[_FuncType[_DeviceT, _P, _R]], _FuncType[_DeviceT, _P, _R | _T]]:
    def wrap(func: _FuncType[_DeviceT, _P, _R]) -> _FuncType[_DeviceT, _P, _R | _T]:
        def wrapped_f(self: _DeviceT, *args: _P.args, **kwargs: _P.kwargs) -> _R | _T:
            if not self.available:
                return ret
            try:
                return func(self, *args, **kwargs)
            except ConnectionError:
                return ret

        return wrapped_f

    return wrap


class ControllerDevice(ClimateEntity):
    """Representation of iZone Controller."""

    _attr_precision = PRECISION_TENTHS
    _attr_should_poll = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = None
    _attr_target_temperature_step = 0.5

    def __init__(self, controller: Controller) -> None:
        """Initialise ControllerDevice."""
        self._controller = controller

        self._attr_supported_features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        # Typically, iZone will automatically set the controller's target
        # temperature; but there are situations where Home Assistant should be
        # allowed to set it:
        #
        # 1. The controller is in RAS mode (i.e., not in master/slave mode).
        # 2. The controller is in master mode, but the control zone is set to
        #    zone 13 (i.e., the master unit itself), or an invalid zone
        #    (greater than the total number of zones). In this case, the
        #    master unit is controlling the temperature directly.
        # 3. Any of the zones do not have a temperature sensor
        if (
            controller.ras_mode == "RAS"
            or (
                controller.ras_mode == "master"
                and controller.zone_ctrl > controller.zones_total
            )
            or any(zone.temp_current is None for zone in controller.zones)
        ):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        self._state_to_pizone = {
            HVACMode.COOL: Controller.Mode.COOL,
            HVACMode.HEAT: Controller.Mode.HEAT,
            HVACMode.HEAT_COOL: Controller.Mode.AUTO,
            HVACMode.FAN_ONLY: Controller.Mode.VENT,
            HVACMode.DRY: Controller.Mode.DRY,
        }
        if controller.free_air_enabled:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        self._fan_to_pizone = {}
        for fan in controller.fan_modes:
            self._fan_to_pizone[_IZONE_FAN_TO_HA[fan]] = fan

        self._attr_unique_id = controller.device_uid
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.device_uid)},
            manufacturer="IZone",
            model=controller.sys_type,
            name=f"iZone Controller {controller.device_uid}",
        )

        # Create the zones
        self.zones = {}
        for zone in controller.zones:
            self.zones[zone] = ZoneDevice(self, zone)

    @override
    async def async_added_to_hass(self) -> None:
        """Call on adding to hass."""

        # Register for connect/disconnect/update events
        @callback
        def controller_disconnected(ctrl: Controller, ex: Exception) -> None:
            """Disconnected from controller."""
            if ctrl is not self._controller:
                return
            self.set_available(False, ex)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCH_CONTROLLER_DISCONNECTED, controller_disconnected
            )
        )

        @callback
        def controller_reconnected(ctrl: Controller) -> None:
            """Reconnected to controller."""
            if ctrl is not self._controller:
                return
            self.set_available(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCH_CONTROLLER_RECONNECTED, controller_reconnected
            )
        )

        @callback
        def controller_update(ctrl: Controller) -> None:
            """Handle controller data updates."""
            if ctrl is not self._controller:
                return
            if not self.available:
                return
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCH_CONTROLLER_UPDATE, controller_update
            )
        )

    @callback
    def set_available(self, available: bool, ex: Exception | None = None) -> None:
        """Set availability for the controller.

        Also sets zone availability as they follow the same availability.
        """
        if self.available == available:
            return

        if available:
            _LOGGER.warning("Reconnected controller %s ", self._controller.device_uid)
        else:
            _LOGGER.warning(
                "Controller %s disconnected due to exception: %s",
                self._controller.device_uid,
                ex,
            )

        self._attr_available = available
        self.async_write_ha_state()
        for zone in self.zones.values():
            if zone.hass is not None:
                zone.async_schedule_update_ha_state()

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the optional state attributes."""
        return {
            "supply_temperature": show_temp(
                self.hass,
                self.supply_temperature,
                self.temperature_unit,
                self.precision,
            ),
            "temp_setpoint": show_temp(
                self.hass,
                self._controller.temp_setpoint,
                self.temperature_unit,
                PRECISION_HALVES,
            ),
            "control_zone": self._controller.zone_ctrl,
            "control_zone_name": self.control_zone_name,
            # Feature ClimateEntityFeature.TARGET_TEMPERATURE controls both displaying
            # target temp & setting it as the feature is turned off for zone control,
            # report target temp as extra state attribute
            "control_zone_setpoint": show_temp(
                self.hass,
                self.control_zone_setpoint,
                self.temperature_unit,
                PRECISION_HALVES,
            ),
        }

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        if not self._controller.is_on:
            return HVACMode.OFF
        if (mode := self._controller.mode) is Controller.Mode.FREE_AIR:
            return HVACMode.FAN_ONLY
        for key, value in self._state_to_pizone.items():
            if value is mode:
                return key
        raise RuntimeError("Should be unreachable")

    @property
    @_return_on_connection_error([])
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation modes."""
        if self._controller.free_air:
            return [HVACMode.OFF, HVACMode.FAN_ONLY]
        return [HVACMode.OFF, *self._state_to_pizone]

    @property
    @_return_on_connection_error(PRESET_NONE)
    @override
    def preset_mode(self) -> str:
        """Eco mode is external air."""
        return PRESET_ECO if self._controller.free_air else PRESET_NONE

    @property
    @_return_on_connection_error([PRESET_NONE])
    @override
    def preset_modes(self) -> list[str]:
        """Available preset modes, normal or eco."""
        if self._controller.free_air_enabled:
            return [PRESET_NONE, PRESET_ECO]
        return [PRESET_NONE]

    @property
    @_return_on_connection_error()
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self._controller.mode is Controller.Mode.FREE_AIR:
            return self._controller.temp_supply
        return self._controller.temp_return

    @property
    def control_zone_name(self):
        """Return the zone that currently controls the AC unit.

        Only relevant if target temp not set by controller.
        """
        if self._attr_supported_features & ClimateEntityFeature.TARGET_TEMPERATURE:
            return None
        zone_ctrl = self._controller.zone_ctrl
        zone = next((z for z in self.zones.values() if z.zone_index == zone_ctrl), None)
        if zone is None:
            return None
        return zone.name

    @property
    def control_zone_setpoint(self) -> float | None:
        """Return the temperature setpoint of the controlling zone.

        Only relevant if target temp not set by controller.
        """
        if self._attr_supported_features & ClimateEntityFeature.TARGET_TEMPERATURE:
            return None
        zone_ctrl = self._controller.zone_ctrl
        zone = next((z for z in self.zones.values() if z.zone_index == zone_ctrl), None)
        if zone is None:
            return None
        return zone.target_temperature

    @property
    @_return_on_connection_error()
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach.

        Either from control zone or master unit.
        """
        if self._attr_supported_features & ClimateEntityFeature.TARGET_TEMPERATURE:
            return self._controller.temp_setpoint
        return self.control_zone_setpoint

    @property
    def supply_temperature(self) -> float | None:
        """Return the current supply, or in duct, temperature."""
        return self._controller.temp_supply

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return _IZONE_FAN_TO_HA[self._controller.fan]

    @property
    @override
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return list(self._fan_to_pizone)

    @property
    @_return_on_connection_error(0.0)
    @override
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._controller.temp_min

    @property
    @_return_on_connection_error(50.0)
    @override
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._controller.temp_max

    async def wrap_and_catch(self, coro):
        """Catch any connection errors and set unavailable."""
        try:
            await coro
        except ConnectionError as ex:
            self.set_available(False, ex)
        else:
            self.set_available(True)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if not self.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE:
            self.async_schedule_update_ha_state(True)
            return
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.wrap_and_catch(self._controller.set_temp_setpoint(temp))

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        fan = self._fan_to_pizone[fan_mode]
        await self.wrap_and_catch(self._controller.set_fan(fan))

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVACMode.OFF:
            await self.wrap_and_catch(self._controller.set_on(False))
            return
        if not self._controller.is_on:
            await self.wrap_and_catch(self._controller.set_on(True))
        if self._controller.free_air:
            return
        mode = self._state_to_pizone[hvac_mode]
        await self.wrap_and_catch(self._controller.set_mode(mode))

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        await self.wrap_and_catch(
            self._controller.set_free_air(preset_mode == PRESET_ECO)
        )

    @override
    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.wrap_and_catch(self._controller.set_on(True))


class ZoneDevice(ClimateEntity):
    """Representation of iZone Zone."""

    _attr_precision = PRECISION_TENTHS
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, controller: ControllerDevice, zone: Zone) -> None:
        """Initialise ZoneDevice."""
        self._controller = controller
        self._zone = zone

        if zone.type is not Zone.Type.AUTO:
            self._state_to_pizone = {
                HVACMode.OFF: Zone.Mode.CLOSE,
                HVACMode.FAN_ONLY: Zone.Mode.OPEN,
            }
        else:
            self._state_to_pizone = {
                HVACMode.OFF: Zone.Mode.CLOSE,
                HVACMode.FAN_ONLY: Zone.Mode.OPEN,
                HVACMode.HEAT_COOL: Zone.Mode.AUTO,
            }
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_unique_id = f"{controller.unique_id}_z{zone.index + 1}"
        assert controller.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, controller.unique_id, zone.index)  # type:ignore[arg-type]
            },
            manufacturer="IZone",
            model=zone.type.name.title(),
            name=zone.name.title(),
            via_device=(DOMAIN, controller.unique_id),
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Call on adding to hass."""

        @callback
        def controller_update(ctrl: Controller) -> None:
            """Handle controller data updates."""
            if ctrl.device_uid != self._controller.unique_id:
                return
            if not self.available:
                return
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCH_CONTROLLER_UPDATE, controller_update
            )
        )

        @callback
        def zone_update(ctrl: Controller, zone: Zone) -> None:
            """Handle zone data updates."""
            if zone is not self._zone:
                return
            if not self.available:
                return
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, DISPATCH_ZONE_UPDATE, zone_update)
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._controller.available

    @property
    @_return_on_connection_error(ClimateEntityFeature(0))
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        if self._zone.mode is Zone.Mode.AUTO:
            return self._attr_supported_features
        return self._attr_supported_features & ~ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation ie. heat, cool, idle."""
        mode = self._zone.mode
        for key, value in self._state_to_pizone.items():
            if value is mode:
                return key
        return None

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation modes."""
        return list(self._state_to_pizone)

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._zone.temp_current

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self._zone.type is not Zone.Type.AUTO:
            return None
        return self._zone.temp_setpoint

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._controller.min_temp

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._controller.max_temp

    @property
    def airflow_min(self):
        """Return the minimum air flow."""
        return self._zone.airflow_min

    @property
    def airflow_max(self):
        """Return the maximum air flow."""
        return self._zone.airflow_max

    async def async_set_airflow_min(self, **kwargs):
        """Set new airflow minimum."""
        await self._controller.wrap_and_catch(
            self._zone.set_airflow_min(int(kwargs[ATTR_AIRFLOW]))
        )
        self.async_write_ha_state()

    async def async_set_airflow_max(self, **kwargs):
        """Set new airflow maximum."""
        await self._controller.wrap_and_catch(
            self._zone.set_airflow_max(int(kwargs[ATTR_AIRFLOW]))
        )
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if self._zone.mode is not Zone.Mode.AUTO:
            return
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._controller.wrap_and_catch(self._zone.set_temp_setpoint(temp))

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        mode = self._state_to_pizone[hvac_mode]
        await self._controller.wrap_and_catch(self._zone.set_mode(mode))
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return self._zone.mode is not Zone.Mode.CLOSE

    @override
    async def async_turn_on(self) -> None:
        """Turn device on (open zone)."""
        if self._zone.type is Zone.Type.AUTO:
            await self._controller.wrap_and_catch(self._zone.set_mode(Zone.Mode.AUTO))
        else:
            await self._controller.wrap_and_catch(self._zone.set_mode(Zone.Mode.OPEN))
        self.async_write_ha_state()

    @override
    async def async_turn_off(self) -> None:
        """Turn device off (close zone)."""
        await self._controller.wrap_and_catch(self._zone.set_mode(Zone.Mode.CLOSE))
        self.async_write_ha_state()

    @property
    def zone_index(self):
        """Return the zone index for matching to CtrlZone."""
        return self._zone.index

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the optional state attributes."""
        return {
            "airflow_max": self._zone.airflow_max,
            "airflow_min": self._zone.airflow_min,
            "zone_index": self.zone_index,
        }
