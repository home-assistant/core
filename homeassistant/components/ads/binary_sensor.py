"""Support for ADS binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOVING,
    BinarySensorEntity,
)
from homeassistant.const import CONF_BINARY_SENSORS, CONF_DEVICE_CLASS, CONF_NAME

from . import CONF_ADS_VAR, DATA_ADS, STATE_KEY_STATE, AdsEntity


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Binary Sensor platform for ADS."""
    entities = []

    if discovery_info is None:  # pragma: no cover
        return

    ads_hub = hass.data.get(DATA_ADS)

    for entry in discovery_info[CONF_BINARY_SENSORS]:
        ads_var = entry.get(CONF_ADS_VAR)
        name = entry.get(CONF_NAME)
        device_class = entry.get(CONF_DEVICE_CLASS)
        entities.append(AdsBinarySensor(ads_hub, name, ads_var, device_class))

    add_entities(entities)


class AdsBinarySensor(AdsEntity, BinarySensorEntity):
    """Representation of ADS binary sensors."""

    def __init__(self, ads_hub, name, ads_var, device_class):
        """Initialize ADS binary sensor."""
        super().__init__(ads_hub, name, ads_var)
        self._attr_device_class = device_class or DEVICE_CLASS_MOVING

    async def async_added_to_hass(self):
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, self._ads_hub.PLCTYPE_BOOL)

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]
