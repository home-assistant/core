"""Support for ADS sensors."""
from homeassistant.components import ads
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import CONF_STATE_CLASS
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SENSORS,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers.typing import StateType

from . import CONF_ADS_FACTOR, CONF_ADS_TYPE, CONF_ADS_VAR, STATE_KEY_STATE, AdsEntity


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an ADS sensor device."""
    entities = []

    if discovery_info is None:  # pragma: no cover
        return

    ads_hub = hass.data.get(ads.DATA_ADS)

    for entry in discovery_info[CONF_SENSORS]:
        ads_var = entry.get(CONF_ADS_VAR)
        ads_type = entry.get(CONF_ADS_TYPE)
        name = entry.get(CONF_NAME)
        unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        factor = entry.get(CONF_ADS_FACTOR)
        device_class = entry.get(CONF_DEVICE_CLASS)
        state_class = entry.get(CONF_STATE_CLASS)
        entities.append(
            AdsSensor(
                ads_hub,
                ads_var,
                ads_type,
                name,
                unit_of_measurement,
                factor,
                device_class,
                state_class,
            )
        )

    add_entities(entities)


class AdsSensor(AdsEntity, SensorEntity):
    """Representation of an ADS sensor entity."""

    def __init__(
        self,
        ads_hub,
        ads_var,
        ads_type,
        name,
        unit_of_measurement,
        factor,
        device_class,
        state_class,
    ):
        """Initialize AdsSensor entity."""
        super().__init__(ads_hub, name, ads_var)
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._ads_type = ads_type
        self._factor = factor
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    async def async_added_to_hass(self):
        """Register device notification."""
        await self.async_initialize_device(
            self._ads_var,
            self._ads_hub.ADS_TYPEMAP[self._ads_type],
            STATE_KEY_STATE,
            self._factor,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self._state_dict[STATE_KEY_STATE]
