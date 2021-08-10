"""Platform for climate integration."""
from __future__ import annotations

from typing import Any

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devolo_multi_level_switch import DevoloMultiLevelSwitchDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all cover devices and setup them via config entry."""
    entities = []

    for gateway in hass.data[DOMAIN][entry.entry_id]["gateways"]:
        for device in gateway.multi_level_switch_devices:
            for multi_level_switch in device.multi_level_switch_property:
                if device.device_model_uid in (
                    "devolo.model.Thermostat:Valve",
                    "devolo.model.Room:Thermostat",
                    "devolo.model.Eurotronic:Spirit:Device",
                ):
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

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a climate entity within devolo Home Control."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._attr_hvac_mode = HVAC_MODE_HEAT
        self._attr_hvac_modes = [HVAC_MODE_HEAT]
        self._attr_min_temp = self._multi_level_switch_property.min
        self._attr_max_temp = self._multi_level_switch_property.max
        self._attr_precision = PRECISION_TENTHS
        self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE
        self._attr_target_temperature_step = PRECISION_HALVES
        self._attr_temperature_unit = TEMP_CELSIUS

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

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Do nothing as devolo devices do not support changing the hvac mode."""

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        self._multi_level_switch_property.set(kwargs[ATTR_TEMPERATURE])
