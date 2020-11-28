"""Support for deCONZ climate devices."""
from pydeconz.sensor import Thermostat

from homeassistant.components.climate import DOMAIN, ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import ATTR_OFFSET, ATTR_VALVE, NEW_SENSOR
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

HVAC_MODES = {
    HVAC_MODE_AUTO: "auto",
    HVAC_MODE_COOL: "cool",
    HVAC_MODE_HEAT: "heat",
    HVAC_MODE_OFF: "off",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ climate devices.

    Thermostats are based on the same device class as sensors in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_climate(sensors):
        """Add climate devices from deCONZ."""
        entities = []

        for sensor in sensors:

            if (
                sensor.type in Thermostat.ZHATYPE
                and sensor.uniqueid not in gateway.entities[DOMAIN]
                and (
                    gateway.option_allow_clip_sensor
                    or not sensor.type.startswith("CLIP")
                )
            ):
                entities.append(DeconzThermostat(sensor, gateway))

        if entities:
            async_add_entities(entities)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_SENSOR), async_add_climate
        )
    )

    async_add_climate(gateway.api.sensors.values())


class DeconzThermostat(DeconzDevice, ClimateEntity):
    """Representation of a deCONZ thermostat."""

    TYPE = DOMAIN

    def __init__(self, device, gateway):
        """Set up thermostat device."""
        super().__init__(device, gateway)

        self._hvac_modes = dict(HVAC_MODES)
        if "coolsetpoint" not in device.raw["config"]:
            self._hvac_modes.pop(HVAC_MODE_COOL)

        self._features = SUPPORT_TARGET_TEMPERATURE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._features

    # HVAC control

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        for hass_hvac_mode, device_mode in self._hvac_modes.items():
            if self._device.mode == device_mode:
                return hass_hvac_mode

        if self._device.state_on:
            return HVAC_MODE_HEAT

        return HVAC_MODE_OFF

    @property
    def hvac_modes(self) -> list:
        """Return the list of available hvac operation modes."""
        return list(self._hvac_modes)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in self._hvac_modes:
            raise ValueError(f"Unsupported HVAC mode {hvac_mode}")

        data = {"mode": self._hvac_modes[hvac_mode]}

        await self._device.async_set_config(data)

    # Temperature control

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._device.temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        if self._device.mode == "cool":
            return self._device.coolsetpoint
        return self._device.heatsetpoint

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            raise ValueError(f"Expected attribute {ATTR_TEMPERATURE}")

        data = {"heatsetpoint": kwargs[ATTR_TEMPERATURE] * 100}
        if self._device.mode == "cool":
            data = {"coolsetpoint": kwargs[ATTR_TEMPERATURE] * 100}

        await self._device.async_set_config(data)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the thermostat."""
        attr = {}

        if self._device.offset:
            attr[ATTR_OFFSET] = self._device.offset

        if self._device.valve is not None:
            attr[ATTR_VALVE] = self._device.valve

        return attr
