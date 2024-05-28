"""Platform for climate integration."""

from __future__ import annotations

from typing import Any

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DevoloHomeControlConfigEntry
from .devolo_multi_level_switch import DevoloMultiLevelSwitchDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Get all cover devices and setup them via config entry."""

    async_add_entities(
        DevoloClimateDeviceEntity(
            homecontrol=gateway,
            device_instance=device,
            element_uid=multi_level_switch,
        )
        for gateway in entry.runtime_data
        for device in gateway.multi_level_switch_devices
        for multi_level_switch in device.multi_level_switch_property
        if device.device_model_uid
        in (
            "devolo.model.Thermostat:Valve",
            "devolo.model.Room:Thermostat",
            "devolo.model.Eurotronic:Spirit:Device",
            "unk.model.Danfoss:Thermostat",
        )
    )


class DevoloClimateDeviceEntity(DevoloMultiLevelSwitchDeviceEntity, ClimateEntity):
    """Representation of a climate/thermostat device within devolo Home Control."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_TENTHS
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a climate entity within devolo Home Control."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._attr_min_temp = self._multi_level_switch_property.min
        self._attr_max_temp = self._multi_level_switch_property.max

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

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Do nothing as devolo devices do not support changing the hvac mode."""

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        self._multi_level_switch_property.set(kwargs[ATTR_TEMPERATURE])
