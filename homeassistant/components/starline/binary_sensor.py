"""Reads vehicle status from StarLine API."""
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASS_OPENING,
    DEVICE_CLASS_LOCK, DEVICE_CLASS_PROBLEM, DEVICE_CLASS_POWER)
from .const import DOMAIN

SENSOR_TYPES = {
    "hbrake": ["Hand Brake", DEVICE_CLASS_POWER, "mdi:car-brake-parking", "mdi:car-brake-parking"],
    "hood": ["Hood", DEVICE_CLASS_OPENING, "mdi:car", "mdi:car"],
    "trunk": ["Trunk", DEVICE_CLASS_OPENING, "mdi:car-back", "mdi:car-back"],
    "alarm": ["Alarm", DEVICE_CLASS_PROBLEM, "mdi:car-connected", "mdi:car"],
    "door": ["Doors", DEVICE_CLASS_LOCK, "mdi:car-door", "mdi:car-door-lock"],
    "ign": ["Engine", DEVICE_CLASS_POWER, "mdi:engine-outline", "mdi:engine-off-outline"],
    "run": ["Ignition", DEVICE_CLASS_POWER, "mdi:key", "mdi:key-remove"],
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine sensors."""
    api = hass.data[DOMAIN]
    entities = []
    for device_id, device in api.devices.items():
        for key, value in SENSOR_TYPES.items():
            if key in device.car_state:
                entities.append(StarlineSensor(api, device, key, *value))
    async_add_entities(entities)
    return True


class StarlineSensor(BinarySensorDevice):
    """Representation of a StarLine binary sensor."""
    def __init__(self, api, device, key, sensor_name, device_class, icon_on, icon_off):
        """Constructor."""
        self._api = api
        self._device = device
        self._key = key
        self._sensor_name = sensor_name
        self._device_class = device_class
        self._icon_on = icon_on
        self._icon_off = icon_off

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return f"starline-{self._key}-{str(self._device.device_id)}"

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"{self._device.name} {self._sensor_name}"

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

    @property
    def device_info(self):
        """Return the device info."""
        return self._device.device_info

    def update(self):
        """Read new state data."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self._api.add_update_listener(self.update)
