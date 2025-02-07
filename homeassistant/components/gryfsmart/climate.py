"""Handle the Gryf Smart Climate platform."""

from typing import Any

from pygryfsmart.device import _GryfDevice, _GryfThermostat

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_API,
    CONF_DEVICES,
    CONF_EXTRA,
    CONF_HYSTERESIS,
    CONF_ID,
    CONF_NAME,
    CONF_OUT_ID,
    CONF_TEMP_ID,
    CONF_TYPE,
    DOMAIN,
    PLATFORM_THERMOSTAT,
)
from .entity import GryfConfigFlowEntity, GryfYamlEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up the climate platform."""

    climates = []

    for conf in hass.data[DOMAIN].get(PLATFORM_THERMOSTAT):
        device = _GryfThermostat(
            conf.get(CONF_NAME),
            conf.get(CONF_OUT_ID) // 10,
            conf.get(CONF_OUT_ID) % 10,
            conf.get(CONF_TEMP_ID) // 10,
            conf.get(CONF_TEMP_ID) % 10,
            conf.get(CONF_HYSTERESIS, 0),
            hass.data[DOMAIN][CONF_API],
        )
        climates.append(GryfYamlThermostate(device))

    async_add_entities(climates)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config flow for Climate platform."""

    climates = []

    for conf in config_entry.data[CONF_DEVICES]:
        if conf.get(CONF_TYPE) == Platform.CLIMATE:
            device = _GryfThermostat(
                conf.get(CONF_NAME),
                conf.get(CONF_ID) // 10,
                conf.get(CONF_ID) % 10,
                int(conf.get(CONF_EXTRA)) // 10,
                int(conf.get(CONF_EXTRA)) % 10,
                0,
                config_entry.runtime_data[CONF_API],
            )
            climates.append(GryfConfigFlowThermostat(device, config_entry))

    async_add_entities(climates)


class _GryfClimateThermostatBase(ClimateEntity):
    """Gryf thermostat climate base."""

    _device: _GryfThermostat
    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_hvac_action = HVACAction.OFF
    _attr_target_temperature_high = 40
    _attr_target_temperature_low = 5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    _temperature = 85.0
    _target_temperature = 0.0

    async def async_update(self, state):
        """Update state."""

        self._attr_hvac_action = HVACAction.HEATING if state["out"] else HVACAction.OFF
        self._temperature = state["temp"]
        self.async_write_ha_state()

    @property
    def current_temperature(self) -> float | None:
        return self._temperature

    @property
    def target_temperature(self) -> float:
        return self._target_temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""

        if hvac_mode == HVACMode.OFF:
            self._device.enable(False)
            self._attr_hvac_mode = HVACMode.OFF

        elif hvac_mode == HVACMode.HEAT:
            self._device.enable(True)
            self._attr_hvac_mode = HVACMode.HEAT

        self.async_write_ha_state()

    def turn_on(self):
        """Turn the entity on."""

        self._device.enable(True)
        self._attr_hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()

    def turn_off(self):
        """Turn the entity off."""

        self._device.enable(False)
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()

    def toggle(self):
        """Toggle the entity."""

        if self._attr_hvac_mode == HVACMode.OFF:
            self.turn_on()
        else:
            self.turn_off()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temperature = kwargs.get("temperature", 0.0)

        self._target_temperature = temperature
        self._device.set_target_temperature(temperature)


class GryfConfigFlowThermostat(GryfConfigFlowEntity, _GryfClimateThermostatBase):
    """Gryf Smart config flow thermostat class."""

    def __init__(
        self,
        device: _GryfDevice,
        config_entry: ConfigEntry,
    ) -> None:
        """Init the gryf thermostat."""
        super().__init__(config_entry, device)
        device.subscribe(self.async_update)


class GryfYamlThermostate(GryfYamlEntity, _GryfClimateThermostatBase):
    """Gryf smart yaml thermostat class."""

    def __init__(self, device: _GryfDevice) -> None:
        """Init the gryf thermostat."""
        super().__init__(device)
        device.subscribe(self.async_update)
