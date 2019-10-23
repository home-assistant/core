"""Reads vehicle status from StarLine API."""
from homeassistant.components.binary_sensor import (
    BinarySensorDevice,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_POWER,
)
from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

SENSOR_TYPES = {
    "hbrake": [
        "Hand Brake",
        DEVICE_CLASS_POWER,
        "mdi:car-brake-parking",
        "mdi:car-brake-parking",
    ],
    "hood": ["Hood", DEVICE_CLASS_OPENING, "mdi:car", "mdi:car"],
    "trunk": ["Trunk", DEVICE_CLASS_OPENING, "mdi:car-back", "mdi:car-back"],
    "alarm": ["Alarm", DEVICE_CLASS_PROBLEM, "mdi:car-connected", "mdi:car"],
    "door": ["Doors", DEVICE_CLASS_LOCK, "mdi:car-door", "mdi:car-door-lock"],
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine sensors."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in account.api.devices.values():
        for key, value in SENSOR_TYPES.items():
            if key in device.car_state:
                entities.append(StarlineSensor(account, device, key, *value))
    async_add_entities(entities)
    return True


class StarlineSensor(StarlineEntity, BinarySensorDevice):
    """Representation of a StarLine binary sensor."""

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        key: str,
        name: str,
        device_class: str,
        icon_on: str,
        icon_off: str,
    ):
        """Constructor."""
        super().__init__(account, device, key, name)
        self._device_class = device_class
        self._icon_on = icon_on
        self._icon_off = icon_off

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon_on if self.is_on else self._icon_off

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._device.car_state[self._key]
