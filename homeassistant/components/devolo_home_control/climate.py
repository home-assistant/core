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
from .devolo_device import DevoloDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all cover devices and setup them via config entry."""
    entities = []

    for device in hass.data[DOMAIN]["homecontrol"].multi_level_switch_devices:
        for multi_level_switch in device.multi_level_switch_property:
            if device.deviceModelUID in [
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


class DevoloClimateDeviceEntity(DevoloDeviceEntity, ClimateEntity):
    """Representation of a climate/thermostat device within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid):
        """Initialize a devolo climate/thermostat device."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
            name=device_instance.item_name,
            sync=self._sync,
        )

        self._multi_level_switch_property = (
            device_instance.multi_level_switch_property.get(element_uid)
        )

        self._temperature = self._multi_level_switch_property.value

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._temperature

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

    def _sync(self, message=None):
        """Update the climate entity triggered by web socket connection."""
        if message[0] == self._unique_id:
            self._temperature = message[1]
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("Not valid message received: %s", message)
        self.schedule_update_ha_state()
