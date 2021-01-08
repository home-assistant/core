"""Reads vehicle status from StarLine API."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

SENSOR_TYPES = {
    "hbrake": ["Hand Brake", DEVICE_CLASS_POWER],
    "hood": ["Hood", DEVICE_CLASS_DOOR],
    "trunk": ["Trunk", DEVICE_CLASS_DOOR],
    "alarm": ["Alarm", DEVICE_CLASS_PROBLEM],
    "door": ["Doors", DEVICE_CLASS_LOCK],
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine sensors."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in account.api.devices.values():
        for key, value in SENSOR_TYPES.items():
            if key in device.car_state:
                sensor = StarlineSensor(account, device, key, *value)
                if sensor.is_on is not None:
                    entities.append(sensor)
    async_add_entities(entities)


class StarlineSensor(StarlineEntity, BinarySensorEntity):
    """Representation of a StarLine binary sensor."""

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        key: str,
        name: str,
        device_class: str,
    ):
        """Initialize sensor."""
        super().__init__(account, device, key, name)
        self._device_class = device_class

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._device.car_state.get(self._key)
