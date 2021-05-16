"""Platform for climate integration."""
from __future__ import annotations

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
    TEMP_CELSIUS,
    ClimateEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .devolo_multi_level_switch import DevoloMultiLevelSwitchDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all cover devices and setup them via config entry."""
    entities = []

    for gateway in hass.data[DOMAIN][entry.entry_id]["gateways"]:
        for device in gateway.multi_level_switch_devices:
            for multi_level_switch in device.multi_level_switch_property:
                if device.device_model_uid in [
                    "devolo.model.Thermostat:Valve",
                    "devolo.model.Room:Thermostat",
                    "devolo.model.Eurotronic:Spirit:Device",
                ]:
                    entities.append(
                        DevoloClimateDeviceEntity(
                            homecontrol=gateway,
                            device_instance=device,
                            element_uid=multi_level_switch,
                        )
                    )

    async_add_entities(entities, False)


class DevoloClimateDeviceEntity(DevoloMultiLevelSwitchDeviceEntity, ClimateEntity):
    """Representation of a climate/thermostat device within devolo Home Control."""

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if hasattr(self._device_instance, "multi_level_sensor_property"):
            return next(
                (
                    multi_level_sensor.value
                    for multi_level_sensor in self._device_instance.multi_level_sensor_property.values()
                    if multi_level_sensor.sensor_type == "temperature"
                ),
                None,
            )

        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._value

    @property
    def target_temperature_step(self) -> float:
        """Return the precision of the target temperature."""
        return PRECISION_HALVES

    @property
    def hvac_mode(self) -> str:
        """Return the supported HVAC mode."""
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT]

    @property
    def min_temp(self) -> float:
        """Return the minimum set temperature value."""
        return self._multi_level_switch_property.min

    @property
    def max_temp(self) -> float:
        """Return the maximum set temperature value."""
        return self._multi_level_switch_property.max

    @property
    def precision(self) -> float:
        """Return the precision of the set temperature."""
        return PRECISION_TENTHS

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self) -> str:
        """Return the supported unit of temperature."""
        return TEMP_CELSIUS

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Do nothing as devolo devices do not support changing the hvac mode."""

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        self._multi_level_switch_property.set(kwargs[ATTR_TEMPERATURE])
