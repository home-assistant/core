"""Support for the Daikin BRP069A62."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin water tank entities."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    for device in (coordinator.data or {}).values():
        supported_management_point_types = (
            "domesticHotWaterTank",
            "domesticHotWaterFlowThrough",
        )
        for management_point_type in supported_management_point_types:
            for management_point in device.device.management_points_by_type(
                management_point_type
            ):
                async_add_entities(
                    [
                        DaikinWaterTank(
                            device,
                            coordinator,
                            management_point_type,
                            management_point.embedded_id,
                        )
                    ]
                )


class DaikinWaterTank(CoordinatorEntity, WaterHeaterEntity):
    """Representation of a Daikin Water Tank."""

    def __init__(self, device, coordinator, management_point_type, embedded_id) -> None:
        """Initialize the Water device."""
        _LOGGER.info("Initializing Daiking Altherma HotWaterTank")
        super().__init__(coordinator)
        self._device = device
        self._embedded_id = embedded_id
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_unique_id = f"{self._device.id}_{self._embedded_id}"
        self._management_point_type = management_point_type
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device.id + embedded_id)},
            "name": self._device.name,
            "via_device_id": self._device.ha_device_id,
        }
        self._device.fill_device_info(self._attr_device_info, embedded_id)
        self._attr_has_entity_name = True
        self.update_state()
        if self.supported_features & WaterHeaterEntityFeature.TARGET_TEMPERATURE:
            _LOGGER.debug("Device '%s' tank temperature is settable", device.name)

    def update_state(self) -> None:
        """Refresh all state attributes from the device."""
        self._attr_supported_features = self.get_supported_features()
        self._attr_current_temperature = self.get_current_temperature()
        self._attr_target_temperature = self.get_target_temperature()
        self._attr_min_temp = self.get_min_temp()
        self._attr_max_temp = self.get_max_temp()
        self._attr_operation_list = self.get_operation_list()
        self._attr_current_operation = self.get_current_operation()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return super().available and self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    @property
    def hotwatertank_data(self):
        """Return the typed hot-water management point."""
        return self._device.management_point(self._embedded_id)

    @property
    def domestic_hotwater_temperature(self):
        """Return the domestic hot-water temperature setpoint."""
        point = self.hotwatertank_data
        if point is None or point.temperature_control is None:
            return None
        heating = point.temperature_control.value.operation_modes.get("heating")
        if heating is None:
            return None
        return heating.setpoints.get("domesticHotWaterTemperature")

    def get_supported_features(self):
        """Return the list of supported features."""
        sf = WaterHeaterEntityFeature.OPERATION_MODE | WaterHeaterEntityFeature.ON_OFF
        # Only when we have a fixed setpointMode we can control the target
        # temperature of the tank
        dht = self.domestic_hotwater_temperature
        if dht and dht.settable:
            sf |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        return sf

    def get_current_temperature(self):
        """Return tank temperature."""
        ret = None
        hwtd = self.hotwatertank_data
        sensory_data = hwtd.sensory_data if hwtd is not None else None
        tank_temperature = (
            sensory_data.value.tank_temperature if sensory_data is not None else None
        )
        if tank_temperature is not None:
            ret = float(tank_temperature.value)
            _LOGGER.debug(
                "Device '%s' hot water tank current_temperature '%s'",
                self._device.name,
                ret,
            )
        else:
            _LOGGER.debug(
                "Device '%s' doesn't provide a current temperature", self._device.name
            )

        return ret

    def get_target_temperature(self):
        """Return the temperature we try to reach."""
        ret = None
        dht = self.domestic_hotwater_temperature
        if dht is not None:
            ret = float(dht.value)
        _LOGGER.debug(
            "Device '%s' hot water tank target_temperature '%s'", self._device.name, ret
        )
        return ret

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return optional device state attributes."""
        data = {}
        dht = self.domestic_hotwater_temperature
        if dht is not None:
            data = {"target_temp_step": float(dht.step_value)}
        return data

    def get_min_temp(self):
        """Return the supported minimum value target temperature."""
        ret = None
        dht = self.domestic_hotwater_temperature
        if dht is not None:
            ret = float(dht.min_value)
        _LOGGER.debug(
            "Device '%s' hot water tank minimum_temperature '%s'",
            self._device.name,
            ret,
        )
        return ret

    def get_max_temp(self):
        """Return the supported maximum value of target temperature."""
        ret = None
        dht = self.domestic_hotwater_temperature
        if dht is not None:
            ret = float(dht.max_value)
        _LOGGER.debug(
            "Device '%s' hot water tank maximum temperature '%s'",
            self._device.name,
            ret,
        )
        return ret

    async def async_set_tank_temperature(self, value):
        """Set new target temperature."""
        _LOGGER.debug("Device '%s' set tank temperature: %s", self._device.name, value)
        if self.current_operation == STATE_OFF:
            _LOGGER.debug(
                "Device '%s' set tank temperature ignored because device is off",
                self._device.name,
            )
            return
        dht = self.domestic_hotwater_temperature
        if dht is not None and not dht.settable:
            _LOGGER.debug(
                "Device '%s' set tank temperature ignored because tank temperature can't be set",
                self._device.name,
            )
            return

        int_value = int(value)
        if int_value != self._attr_target_temperature:
            res = await self._device.patch(
                self._device.id,
                self._embedded_id,
                "temperatureControl",
                "/operationModes/heating/setpoints/domesticHotWaterTemperature",
                int_value,
            )
            # When updating the value to the daikin cloud worked update our local cached version
            if res:
                self._attr_target_temperature = int_value
                self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        # The service climate.set_temperature can set the hvac_mode too, see
        # https://www.home-assistant.io/integrations/climate/#service-climateset_temperature
        # se we first set the hvac_mode, if provided, then the temperature.
        await self.async_set_tank_temperature(kwargs[ATTR_TEMPERATURE])

    def get_current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        state = STATE_OFF
        hwtd = self.hotwatertank_data
        onoff = hwtd.on_off_mode if hwtd is not None else None
        if onoff is not None and onoff.value == "on":
            state = STATE_HEAT_PUMP
            pwf = hwtd.characteristic("powerfulMode") if hwtd is not None else None
            if pwf is not None and pwf.value == "on":
                state = STATE_PERFORMANCE
        _LOGGER.debug(
            "Device '%s' hot water tank current mode '%s'", self._device.name, state
        )
        return state

    def get_operation_list(self):
        """Return the list of available operation modes."""
        states = [STATE_OFF, STATE_HEAT_PUMP]
        hwtd = self.hotwatertank_data
        pwf = hwtd.characteristic("powerfulMode") if hwtd is not None else None
        if pwf is not None and pwf.settable:
            states += [STATE_PERFORMANCE]
        _LOGGER.debug(
            "Device '%s' hot water tank supports modes %s", self._device.name, states
        )
        return states

    def _requested_modes(self, operation_mode: str) -> tuple[str, str]:
        """Return the required on/off and powerful-mode values."""
        on_off_mode = ""
        powerful_mode = ""
        if operation_mode == STATE_OFF:
            on_off_mode = "off"
        elif operation_mode == STATE_PERFORMANCE:
            powerful_mode = "on"
            on_off_mode = "on" if self.current_operation == STATE_OFF else ""
        elif operation_mode == STATE_HEAT_PUMP:
            powerful_mode = "off" if self.current_operation == STATE_PERFORMANCE else ""
            on_off_mode = "on" if self.current_operation == STATE_OFF else ""
        return on_off_mode, powerful_mode

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new tank state."""
        _LOGGER.debug("Set tank operation mode: %s", operation_mode)
        result = True

        # First determine the new settings for onOffMode/powerfulMode, we need these to set them to Daikin
        # and update our local cached version when succeeded
        on_off_mode, powerful_mode = self._requested_modes(operation_mode)

        # Only set the on/off to Daikin when we need to change it
        if on_off_mode != "":
            result &= await self._device.patch(
                self._device.id, self._embedded_id, "onOffMode", "", on_off_mode
            )
            if result is True:
                hwtd = self.hotwatertank_data
                if hwtd is not None and hwtd.on_off_mode is not None:
                    hwtd.on_off_mode.value = on_off_mode

        # Only set powerfulMode when it is set and supported by the device
        if powerful_mode != "" and STATE_PERFORMANCE in (self.operation_list or []):
            result &= await self._device.patch(
                self._device.id,
                self._embedded_id,
                "powerfulMode",
                "",
                powerful_mode,
            )
            if result is True:
                hwtd = self.hotwatertank_data
                pwf = hwtd.characteristic("powerfulMode") if hwtd is not None else None
                if pwf is not None and pwf.settable:
                    pwf.value = powerful_mode

        if result is False:
            _LOGGER.warning(
                "Device '%s' invalid tank state: %s", self._device.name, operation_mode
            )
        else:
            # Update local cached version
            self._attr_current_operation = operation_mode
            self._attr_operation_list = self.get_operation_list()
            self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn water heater on."""
        _LOGGER.debug("Device '%s' request to turn on", self._device.name)
        result = True
        if self.current_operation == STATE_OFF:
            result &= await self._device.patch(
                self._device.id, self._embedded_id, "onOffMode", "", "on"
            )
            if result is False:
                _LOGGER.error(
                    "Device '%s' problem setting onOffMode to on", self._device.name
                )
            else:
                hwtd = self.hotwatertank_data
                if hwtd is not None and hwtd.on_off_mode is not None:
                    hwtd.on_off_mode.value = "on"
                self._attr_current_operation = self.get_current_operation()
                self._attr_operation_list = self.get_operation_list()
                self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device '%s' request to turn on ignored because device is already on",
                self._device.name,
            )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn water heater off."""
        _LOGGER.debug("Device '%s' request to turn off", self._device.name)
        result = True
        if self.current_operation != STATE_OFF:
            result &= await self._device.patch(
                self._device.id, self._embedded_id, "onOffMode", "", "off"
            )
            if result is False:
                _LOGGER.error(
                    "Device '%s' problem setting onOffMode to off", self._device.name
                )
            else:
                hwtd = self.hotwatertank_data
                if hwtd is not None and hwtd.on_off_mode is not None:
                    hwtd.on_off_mode.value = "off"
                self._attr_current_operation = self.get_current_operation()
                self._attr_operation_list = self.get_operation_list()
                self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device '%s' request to turn off ignored because device is already off",
                self._device.name,
            )
