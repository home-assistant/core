"""Platform for climate integration."""
import logging
from typing import List, Optional

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
    TEMP_CELSIUS,
    ClimateEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_HALVES
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .devolo_multi_level_switch import DevoloMultiLevelSwitchDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all cover devices and setup them via config entry."""
    entities = []

    for device in hass.data[DOMAIN]["homecontrol"].multi_level_switch_devices:
        for multi_level_switch in device.multi_level_switch_property:
            if device.device_model_uid in [
                "devolo.model.Thermostat:Valve",
                "devolo.model.Room:Thermostat",
            ]:
                entities.append(
                    DevoloClimateDeviceEntity(
                        homecontrol=hass.data[DOMAIN]["homecontrol"],
                        device_instance=device,
                        element_uid=multi_level_switch,
                    )
                )

    async_add_entities(entities, False)


class DevoloClimateDeviceEntity(DevoloMultiLevelSwitchDeviceEntity, ClimateEntity):
    """Representation of a climate/thermostat device within devolo Home Control."""

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._value

    @property
    def hvac_mode(self) -> str:
        """Return the supported HVAC mode."""
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> List[str]:
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
        return PRECISION_HALVES

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self) -> str:
        """Return the supported unit of temperature."""
        return TEMP_CELSIUS

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        self._multi_level_switch_property.set(kwargs[ATTR_TEMPERATURE])
