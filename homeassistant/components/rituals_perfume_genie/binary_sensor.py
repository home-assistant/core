"""Support for Rituals Perfume Genie binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    BinarySensorEntity,
)

from .const import BATTERY, COORDINATORS, DEVICES, DOMAIN, HUB, ID
from .entity import SENSORS, DiffuserEntity

CHARGING_SUFFIX = " Battery Charging"
BATTERY_CHARGING_ID = 21


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the diffuser binary sensors."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for hublot, diffuser in diffusers.items():
        if BATTERY in diffuser.data[HUB][SENSORS]:
            coordinator = coordinators[hublot]
            entities.append(DiffuserBatteryChargingBinarySensor(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserBatteryChargingBinarySensor(DiffuserEntity, BinarySensorEntity):
    """Representation of a diffuser battery charging binary sensor."""

    def __init__(self, diffuser, coordinator):
        """Initialize the battery charging binary sensor."""
        super().__init__(diffuser, coordinator, CHARGING_SUFFIX)

    @property
    def is_on(self):
        """Return the state of the battery charging binary sensor."""
        return bool(
            self.coordinator.data[HUB][SENSORS][BATTERY][ID] == BATTERY_CHARGING_ID
        )

    @property
    def device_class(self):
        """Return the device class of the battery charging binary sensor."""
        return DEVICE_CLASS_BATTERY_CHARGING
