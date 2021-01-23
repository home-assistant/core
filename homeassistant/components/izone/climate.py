"""Support for the iZone HVAC."""
import logging
from typing import List, Optional

from pizone import Controller, Zone

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
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
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_EXCLUDE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    DATA_CONFIG,
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_ZONE_UPDATE,
    IZONE,
)

_LOGGER = logging.getLogger(__name__)

_IZONE_FAN_TO_HA = {
    Controller.Fan.LOW: FAN_LOW,
    Controller.Fan.MED: FAN_MEDIUM,
    Controller.Fan.HIGH: FAN_HIGH,
    Controller.Fan.AUTO: FAN_AUTO,
}


async def async_setup_entry(
    hass: HomeAssistantType, config: ConfigType, async_add_entities
):
    """Initialize an IZone Controller."""
    disco = hass.data[DATA_DISCOVERY_SERVICE]

    @callback
    def init_controller(ctrl: Controller):
        """Register the controller device and the containing zones."""
        conf = hass.data.get(DATA_CONFIG)  # type: ConfigType

        # Filter out any entities excluded in the config file
        if conf and ctrl.device_uid in conf[CONF_EXCLUDE]:
            _LOGGER.info("Controller UID=%s ignored as excluded", ctrl.device_uid)
            return
        _LOGGER.info("Controller UID=%s discovered", ctrl.device_uid)

        device = ControllerDevice(ctrl)
        async_add_entities([device])
        async_add_entities(device.zones.values())

    # create any components not yet created
    for controller in disco.pi_disco.controllers.values():
        init_controller(controller)

    # connect to register any further components
    async_dispatcher_connect(hass, DISPATCH_CONTROLLER_DISCOVERED, init_controller)

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


class ControllerDevice(ClimateEntity):
    """Representation of iZone Controller."""

    def __init__(self, controller: Controller) -> None:
        """Initialise ControllerDevice."""
        self._controller = controller

        self._supported_features = SUPPORT_FAN_MODE

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

        self._device_info = {
            "identifiers": {(IZONE, self.unique_id)},
            "name": self.name,
            "manufacturer": "IZone",
            "model": self._controller.sys_type,
        }

        # Create the zones
        self.zones = {}
        for zone in controller.zones:
            self.zones[zone] = ZoneDevice(self, zone)

    async def async_added_to_hass(self):
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
            self.async_write_ha_state()
            for zone in self.zones.values():
                zone.async_schedule_update_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCH_CONTROLLER_UPDATE, controller_update
            )
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @callback
    def set_available(self, available: bool, ex: Exception = None) -> None:
        """
        Set availability for the controller.

        Also sets zone availability as they follow the same availability.
        """
        if self.available == available:
            return

        if available:
            _LOGGER.info("Reconnected controller %s ", self._controller.device_uid)
        else:
            _LOGGER.info(
                "Controller %s disconnected due to exception: %s",
                self._controller.device_uid,
                ex,
            )

        self._available = available
        self.async_write_ha_state()
        for zone in self.zones.values():
            zone.async_schedule_update_ha_state()

    @property
    def device_info(self):
        """Return the device info for the iZone system."""
        return self._device_info

    @property
    def unique_id(self):
        """Return the ID of the controller device."""
        return self._controller.device_uid

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"iZone Controller {self._controller.device_uid}"

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

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
    def device_state_attributes(self):
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
        }

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        if not self._controller.is_on:
            return HVAC_MODE_OFF
        mode = self._controller.mode
        if mode == Controller.Mode.FREE_AIR:
            return HVAC_MODE_FAN_ONLY
        for (key, value) in self._state_to_pizone.items():
            if value == mode:
                return key
        assert False, "Should be unreachable"

    @property
    @_return_on_connection_error([])
    def hvac_modes(self) -> List[str]:
        """Return the list of available operation modes."""
        if self._controller.free_air:
            return [HVAC_MODE_OFF, HVAC_MODE_FAN_ONLY]
        return [HVAC_MODE_OFF, *self._state_to_pizone]

    @property
    @_return_on_connection_error(PRESET_NONE)
    def preset_mode(self):
        """Eco mode is external air."""
        return PRESET_ECO if self._controller.free_air else PRESET_NONE

    @property
    @_return_on_connection_error([PRESET_NONE])
    def preset_modes(self):
        """Available preset modes, normal or eco."""
        if self._controller.free_air_enabled:
            return [PRESET_NONE, PRESET_ECO]
        return [PRESET_NONE]

    @property
    @_return_on_connection_error()
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        if self._controller.mode == Controller.Mode.FREE_AIR:
            return self._controller.temp_supply
        return self._controller.temp_return

    @property
    @_return_on_connection_error()
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        if not self._supported_features & SUPPORT_TARGET_TEMPERATURE:
            return None
        return self._controller.temp_setpoint

    @property
    def supply_temperature(self) -> float:
        """Return the current supply, or in duct, temperature."""
        return self._controller.temp_supply

    @property
    def target_temperature_step(self) -> Optional[float]:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting."""
        return _IZONE_FAN_TO_HA[self._controller.fan]

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return the list of available fan modes."""
        return list(self._fan_to_pizone)

    @property
    @_return_on_connection_error(0.0)
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._controller.temp_min

    @property
    @_return_on_connection_error(50.0)
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

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if not self.supported_features & SUPPORT_TARGET_TEMPERATURE:
            self.async_schedule_update_ha_state(True)
            return
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.wrap_and_catch(self._controller.set_temp_setpoint(temp))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        fan = self._fan_to_pizone[fan_mode]
        await self.wrap_and_catch(self._controller.set_fan(fan))

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.wrap_and_catch(self._controller.set_on(False))
            return
        if not self._controller.is_on:
            await self.wrap_and_catch(self._controller.set_on(True))
        if self._controller.free_air:
            return
        mode = self._state_to_pizone[hvac_mode]
        await self.wrap_and_catch(self._controller.set_mode(mode))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        await self.wrap_and_catch(
            self._controller.set_free_air(preset_mode == PRESET_ECO)
        )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.wrap_and_catch(self._controller.set_on(True))


class ZoneDevice(ClimateEntity):
    """Representation of iZone Zone."""

    def __init__(self, controller: ControllerDevice, zone: Zone) -> None:
        """Initialise ZoneDevice."""
        self._controller = controller
        self._zone = zone
        self._name = zone.name.title()

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

        self._device_info = {
            "identifiers": {(IZONE, controller.unique_id, zone.index)},
            "name": self.name,
            "manufacturer": "IZone",
            "via_device": (IZONE, controller.unique_id),
            "model": zone.type.name.title(),
        }

    async def async_added_to_hass(self):
        """Call on adding to hass."""

        @callback
        def zone_update(ctrl: Controller, zone: Zone) -> None:
            """Handle zone data updates."""
            if zone is not self._zone:
                return
            self._name = zone.name.title()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, DISPATCH_ZONE_UPDATE, zone_update)
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._controller.available

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return self._controller.assumed_state

    @property
    def device_info(self):
        """Return the device info for the iZone system."""
        return self._device_info

    @property
    def unique_id(self):
        """Return the ID of the controller device."""
        return f"{self._controller.unique_id}_z{self._zone.index + 1}"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

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
    def min_temp(self):
        """Return the minimum temperature."""
        return self._controller.min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._controller.max_temp

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if self._zone.mode != Zone.Mode.AUTO:
            return
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self._controller.wrap_and_catch(self._zone.set_temp_setpoint(temp))

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        mode = self._state_to_pizone[hvac_mode]
        await self._controller.wrap_and_catch(self._zone.set_mode(mode))
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if on."""
        return self._zone.mode != Zone.Mode.CLOSE

    async def async_turn_on(self):
        """Turn device on (open zone)."""
        if self._zone.type == Zone.Type.AUTO:
            await self._controller.wrap_and_catch(self._zone.set_mode(Zone.Mode.AUTO))
        else:
            await self._controller.wrap_and_catch(self._zone.set_mode(Zone.Mode.OPEN))
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn device off (close zone)."""
        await self._controller.wrap_and_catch(self._zone.set_mode(Zone.Mode.CLOSE))
        self.async_write_ha_state()
