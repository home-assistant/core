"""Support for monitoring a Sense energy sensor device."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_get_registry

from .const import DOMAIN, SENSE_DATA, SENSE_DEVICE_UPDATE

_LOGGER = logging.getLogger(__name__)

ATTR_WATTS = "watts"
DEVICE_ID_SOLAR = "solar"
BIN_SENSOR_CLASS = "power"
MDI_ICONS = {
    "ac": "air-conditioner",
    "aquarium": "fish",
    "car": "car-electric",
    "computer": "desktop-classic",
    "cup": "coffee",
    "dehumidifier": "water-off",
    "dishes": "dishwasher",
    "drill": "toolbox",
    "fan": "fan",
    "freezer": "fridge-top",
    "fridge": "fridge-bottom",
    "game": "gamepad-variant",
    "garage": "garage",
    "grill": "stove",
    "heat": "fire",
    "heater": "radiatior",
    "humidifier": "water",
    "kettle": "kettle",
    "leafblower": "leaf",
    "lightbulb": "lightbulb",
    "media_console": "set-top-box",
    "modem": "router-wireless",
    "outlet": "power-socket-us",
    "papershredder": "shredder",
    "printer": "printer",
    "pump": "water-pump",
    "settings": "settings",
    "skillet": "pot",
    "smartcamera": "webcam",
    "socket": "power-plug",
    "solar_alt": "solar-power",
    "sound": "speaker",
    "stove": "stove",
    "trash": "trash-can",
    "tv": "television",
    "vacuum": "robot-vacuum",
    "washer": "washing-machine",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Sense binary sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id][SENSE_DATA]
    sense_monitor_id = data.sense_monitor_id

    sense_devices = await data.get_discovered_device_data()
    devices = [
        SenseDevice(data, device, sense_monitor_id)
        for device in sense_devices
        if device["id"] == DEVICE_ID_SOLAR
        or device["tags"]["DeviceListAllowed"] == "true"
    ]

    await _migrate_old_unique_ids(hass, devices)

    async_add_entities(devices)


async def _migrate_old_unique_ids(hass, devices):
    registry = await async_get_registry(hass)
    for device in devices:
        # Migration of old not so unique ids
        old_entity_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, device.old_unique_id
        )
        if old_entity_id is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.old_unique_id,
                device.unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=device.unique_id)


def sense_to_mdi(sense_icon):
    """Convert sense icon to mdi icon."""
    return "mdi:{}".format(MDI_ICONS.get(sense_icon, "power-plug"))


class SenseDevice(BinarySensorDevice):
    """Implementation of a Sense energy device binary sensor."""

    def __init__(self, data, device, sense_monitor_id):
        """Initialize the Sense binary sensor."""
        self._name = device["name"]
        self._id = device["id"]
        self._sense_monitor_id = sense_monitor_id
        self._unique_id = f"{sense_monitor_id}-{self._id}"
        self._icon = sense_to_mdi(device["icon"])
        self._data = data
        self._undo_dispatch_subscription = None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._name in self._data.active_devices

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the binary sensor."""
        return self._unique_id

    @property
    def old_unique_id(self):
        """Return the old not so unique id of the binary sensor."""
        return self._id

    @property
    def icon(self):
        """Return the icon of the binary sensor."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return BIN_SENSOR_CLASS

    @property
    def should_poll(self):
        """Return the deviceshould not poll for updates."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._undo_dispatch_subscription = async_dispatcher_connect(
            self.hass, f"{SENSE_DEVICE_UPDATE}-{self._sense_monitor_id}", update
        )

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        if self._undo_dispatch_subscription:
            self._undo_dispatch_subscription()
