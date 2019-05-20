"""Support for HomematicIP Cloud climate devices."""
import logging

from homematicip.aio.device import (
    AsyncHeatingThermostat, AsyncHeatingThermostatCompact)
from homematicip.aio.group import AsyncHeatingGroup
from homematicip.aio.home import AsyncHome
from homematicip.base.enums import ClimateControlMode

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_MANUAL, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice

_LOGGER = logging.getLogger(__name__)

STATE_BOOST = 'Boost'

HA_STATE_TO_HMIP = {
    STATE_AUTO: ClimateControlMode.AUTOMATIC,
    STATE_MANUAL: ClimateControlMode.MANUAL,
    STATE_BOOST: None
}

HMIP_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_HMIP.items()}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud climate devices."""
    pass


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up the HomematicIP climate from a config entry."""
    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.groups:
        if isinstance(device, AsyncHeatingGroup):
            devices.append(HomematicipHeatingGroup(home, device))

    if devices:
        async_add_entities(devices)


class HomematicipHeatingGroup(HomematicipGenericDevice, ClimateDevice):
    """Representation of a HomematicIP heating group."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize heating group."""
        device.modelType = 'Group-Heating'
        self._simple_heating = None
        if device.actualTemperature is None:
            self._simple_heating = _get_first_heating_thermostat(device)
        super().__init__(home, device)

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._device.setPointTemperature

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        if self._simple_heating:
            return self._simple_heating.valveActualTemperature
        return self._device.actualTemperature

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._device.humidity

    @property
    def current_operation(self) -> str:
        """Return current operation ie. boost, automatic or manual."""
        if self._device.boostMode:
            return STATE_BOOST
        return HMIP_STATE_TO_HA.get(self._device.controlMode)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [x for x in HMIP_STATE_TO_HA.values()]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._device.minTemperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._device.maxTemperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._device.set_point_temperature(temperature)

    async def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        _LOGGER.error("KAROL: %s", operation_mode)
        if operation_mode == STATE_BOOST:
            await self._device.set_boost()
        else:
            await self._device.set_boost(False)
            await self._device.set_control_mode(
                HA_STATE_TO_HMIP[operation_mode])
        self.schedule_update_ha_state()


def _get_first_heating_thermostat(heating_group: AsyncHeatingGroup):
    """Return the first HeatingThermostat from a HeatingGroup."""
    for device in heating_group.devices:
        if isinstance(device, (AsyncHeatingThermostat,
                               AsyncHeatingThermostatCompact)):
            return device
    return None
