"""Support for the iZone HVAC."""
from __future__ import annotations

from contextlib import suppress
import logging

from pizone import Controller, Zone
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_TOP,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.temperature import display_temp as show_temp

from .const import (
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_ZONE_UPDATE,
    IZONE,
)
from .discovery import ControllerCoordinatorEntity, ControllerUpdateCoordinator

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

IZONE_SERVICE_AIRFLOW_SCHEMA = {
    vol.Required(ATTR_AIRFLOW): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100), msg="invalid airflow"
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize an IZone Controller."""
    disco = hass.data[DATA_DISCOVERY_SERVICE]

    @callback
    def init_controller(coordinator: ControllerUpdateCoordinator):
        """Register the controller device and the containing zones."""
        device = ControllerDevice(coordinator)
        async_add_entities([device])
        async_add_entities(
            [ZoneDevice(coordinator, zone) for zone in coordinator.controller.zones]
        )

    disco.async_add_controller_discovered_listener(init_controller)

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

    return True


def _return_on_connection_error(ret=None):
    def wrap(func):
        def wrapped_f(*args, **kwargs):
            if not args[0].available:
                return ret
            try:
                return func(*args, **kwargs)
            except ConnectionError:
                return ret

        return wrapped_f

    return wrap


class ControllerDevice(ControllerCoordinatorEntity, ClimateEntity):
    """Representation of iZone Controller."""

    def __init__(self, coordinator: ControllerUpdateCoordinator) -> None:
        """Initialise ControllerDevice."""
        super().__init__(coordinator)
        self._supported_features = SUPPORT_FAN_MODE

        controller = self.controller
        # If mode RAS, or mode master with CtrlZone 13 then can set master temperature,
        # otherwise the unit determines which zone to use as target. See interface manual p. 8
        if (
            controller.ras_mode == "master" and controller.zone_ctrl == 13
        ) or controller.ras_mode == "RAS":
            self._supported_features |= SUPPORT_TARGET_TEMPERATURE

        self._state_to_pizone = {
            HVAC_MODE_COOL: Controller.Mode.COOL,
            HVAC_MODE_HEAT: Controller.Mode.HEAT,
            HVAC_MODE_HEAT_COOL: Controller.Mode.AUTO,
            HVAC_MODE_FAN_ONLY: Controller.Mode.VENT,
            HVAC_MODE_DRY: Controller.Mode.DRY,
        }
        if controller.free_air_enabled:
            self._supported_features |= SUPPORT_PRESET_MODE

        self._fan_to_pizone = {}
        for fan in controller.fan_modes:
            self._fan_to_pizone[_IZONE_FAN_TO_HA[fan]] = fan
        self._available = True

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = self.controller.device_uid
        self._attr_name = f"iZone Controller {self.controller.device_uid}"

    async def async_added_to_hass(self):
        """Call on adding to hass."""
        await super().async_added_to_hass()
        self.add_dispatcher_update(DISPATCH_CONTROLLER_UPDATE, self.controller)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._supported_features

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def extra_state_attributes(self):
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
                self.controller.temp_setpoint,
                self.temperature_unit,
                PRECISION_HALVES,
            ),
            "control_zone": self.controller.zone_ctrl,
            "control_zone_name": self.control_zone_name,
            # Feature SUPPORT_TARGET_TEMPERATURE controls both displaying target temp & setting it
            # As the feature is turned off for zone control, report target temp as extra state attribute
            "control_zone_setpoint": show_temp(
                self.hass,
                self.control_zone_setpoint,
                self.temperature_unit,
                PRECISION_HALVES,
            ),
        }

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        if not self.controller.is_on:
            return HVAC_MODE_OFF
        if (mode := self.controller.mode) == Controller.Mode.FREE_AIR:
            return HVAC_MODE_FAN_ONLY
        for (key, value) in self._state_to_pizone.items():
            if value == mode:
                return key
        assert False, "Should be unreachable"

    @property
    @_return_on_connection_error([])
    def hvac_modes(self) -> list[str]:
        """Return the list of available operation modes."""
        if self.controller.free_air:
            return [HVAC_MODE_OFF, HVAC_MODE_FAN_ONLY]
        return [HVAC_MODE_OFF, *self._state_to_pizone]

    @property
    @_return_on_connection_error(PRESET_NONE)
    def preset_mode(self):
        """Eco mode is external air."""
        return PRESET_ECO if self.controller.free_air else PRESET_NONE

    @property
    @_return_on_connection_error([PRESET_NONE])
    def preset_modes(self):
        """Available preset modes, normal or eco."""
        if self.controller.free_air_enabled:
            return [PRESET_NONE, PRESET_ECO]
        return [PRESET_NONE]

    @property
    @_return_on_connection_error()
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.controller.mode == Controller.Mode.FREE_AIR:
            return self.controller.temp_supply
        return self.controller.temp_return

    @property
    def control_zone_name(self):
        """Return the zone that currently controls the AC unit (if target temp not set by controller)."""
        if self._supported_features & SUPPORT_TARGET_TEMPERATURE:
            return None
        zone_ctrl = self.controller.zone_ctrl
        zone = next((z for z in self.controller.zones if z.index == zone_ctrl), None)
        if zone is None:
            return None
        return zone.name

    @property
    def control_zone_setpoint(self) -> float | None:
        """Return the temperature setpoint of the zone that currently controls the AC unit (if target temp not set by controller)."""
        if self._supported_features & SUPPORT_TARGET_TEMPERATURE:
            return None
        zone_ctrl = self.controller.zone_ctrl
        zone = next((z for z in self.controller.zones if z.index == zone_ctrl), None)
        if zone is None:
            return None
        return zone.temp_setpoint

    @property
    @_return_on_connection_error()
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach (either from control zone or master unit)."""
        if self._supported_features & SUPPORT_TARGET_TEMPERATURE:
            return self.controller.temp_setpoint
        return self.control_zone_setpoint

    @property
    def supply_temperature(self) -> float:
        """Return the current supply, or in duct, temperature."""
        return self.controller.temp_supply

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return _IZONE_FAN_TO_HA[self.controller.fan]

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return list(self._fan_to_pizone)

    @property
    @_return_on_connection_error(0.0)
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.controller.temp_min

    @property
    @_return_on_connection_error(50.0)
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.controller.temp_max

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if not self.supported_features & SUPPORT_TARGET_TEMPERATURE:
            self.async_schedule_update_ha_state(True)
            return
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            with suppress(ConnectionError):
                await self.controller.set_temp_setpoint(temp)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        fan = self._fan_to_pizone[fan_mode]
        with suppress(ConnectionError):
            await self.controller.set_fan(fan)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        with suppress(ConnectionError):
            if hvac_mode == HVAC_MODE_OFF:
                await self.controller.set_on(False)
                return
            if not self.controller.is_on:
                await self.controller.set_on(True)
            if self.controller.free_air:
                return
            mode = self._state_to_pizone[hvac_mode]
            await self.controller.set_mode(mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        with suppress(ConnectionError):
            await self.controller.set_free_air(preset_mode == PRESET_ECO)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        with suppress(ConnectionError):
            await self.controller.set_on(True)


class ZoneDevice(ControllerCoordinatorEntity, ClimateEntity):
    """Representation of iZone Zone."""

    def __init__(self, coordinator: ControllerUpdateCoordinator, zone: Zone) -> None:
        """Initialise ZoneDevice."""
        super().__init__(coordinator)
        self._zone = zone
        self._supported_features = 0
        if zone.type != Zone.Type.AUTO:
            self._state_to_pizone = {
                HVAC_MODE_OFF: Zone.Mode.CLOSE,
                HVAC_MODE_FAN_ONLY: Zone.Mode.OPEN,
            }
        else:
            self._state_to_pizone = {
                HVAC_MODE_OFF: Zone.Mode.CLOSE,
                HVAC_MODE_FAN_ONLY: Zone.Mode.OPEN,
                HVAC_MODE_HEAT_COOL: Zone.Mode.AUTO,
            }
            self._supported_features |= SUPPORT_TARGET_TEMPERATURE

        self._attr_device_info = DeviceInfo(
            identifiers={(IZONE, self.controller.device_uid, zone.index)},
            manufacturer="IZone",
            model=zone.type.name.title(),
            name=self.name,
            via_device=(IZONE, self.controller.device_uid),
        )
        self._attr_unique_id = f"{self.controller.device_uid}_z{self._zone.index + 1}"

    async def async_added_to_hass(self):
        """Call on adding to hass."""
        await super().async_added_to_hass()
        self.add_dispatcher_update(DISPATCH_ZONE_UPDATE, self.controller, self._zone)

    @property
    def name(self) -> str:
        """Return the name of the zone."""
        try:
            return self._zone.name.title()
        except ConnectionError:
            return f"Zone {self._zone.index}"

    @property
    @_return_on_connection_error(0)
    def supported_features(self):
        """Return the list of supported features."""
        if self._zone.mode == Zone.Mode.AUTO:
            return self._supported_features
        return self._supported_features & ~SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        mode = self._zone.mode
        for (key, value) in self._state_to_pizone.items():
            if value == mode:
                return key
        return None

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return list(self._state_to_pizone)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._zone.temp_current

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._zone.type != Zone.Type.AUTO:
            return None
        return self._zone.temp_setpoint

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    @_return_on_connection_error(0.0)
    def min_temp(self):
        """Return the minimum temperature."""
        return self.controller.temp_min

    @property
    @_return_on_connection_error(50.0)
    def max_temp(self):
        """Return the maximum temperature."""
        return self.controller.temp_max

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
        with suppress(ConnectionError):
            await self._zone.set_airflow_min(int(kwargs[ATTR_AIRFLOW]))

    async def async_set_airflow_max(self, **kwargs):
        """Set new airflow maximum."""
        with suppress(ConnectionError):
            await self._zone.set_airflow_max(int(kwargs[ATTR_AIRFLOW]))

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if self._zone.mode != Zone.Mode.AUTO:
            return
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            with suppress(ConnectionError):
                await self._zone.set_temp_setpoint(temp)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        mode = self._state_to_pizone[hvac_mode]
        with suppress(ConnectionError):
            await self._zone.set_mode(mode)

    @property
    def is_on(self):
        """Return true if on."""
        return self._zone.mode != Zone.Mode.CLOSE

    async def async_turn_on(self):
        """Turn device on (open zone)."""
        with suppress(ConnectionError):
            if self._zone.type == Zone.Type.AUTO:
                await self._zone.set_mode(Zone.Mode.AUTO)
            else:
                await self._zone.set_mode(Zone.Mode.OPEN)

    async def async_turn_off(self):
        """Turn device off (close zone)."""
        with suppress(ConnectionError):
            self._zone.set_mode(Zone.Mode.CLOSE)

    @property
    def zone_index(self):
        """Return the zone index for matching to CtrlZone."""
        return self._zone.index

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        return {
            "airflow_max": self._zone.airflow_max,
            "airflow_min": self._zone.airflow_min,
            "zone_index": self.zone_index,
        }
