"""This component provides HA sensor support for Ring Door Bell/Chimes."""
from itertools import chain
import logging

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import (
    ATTRIBUTION,
    DATA_HEALTH_DATA_TRACKER,
    DOMAIN,
    SIGNAL_UPDATE_HEALTH_RING,
    SIGNAL_UPDATE_RING,
)

_LOGGER = logging.getLogger(__name__)

# Sensor types: Name, category, units, icon, kind, device_class
SENSOR_TYPES = {
    "battery": ["Battery", ["doorbell", "stickup_cams"], "%", None, None, "battery"],
    "last_activity": [
        "Last Activity",
        ["doorbell", "stickup_cams"],
        None,
        "history",
        None,
        "timestamp",
    ],
    "last_ding": ["Last Ding", ["doorbell"], None, "history", "ding", "timestamp"],
    "last_motion": [
        "Last Motion",
        ["doorbell", "stickup_cams"],
        None,
        "history",
        "motion",
        "timestamp",
    ],
    "volume": [
        "Volume",
        ["chime", "doorbell", "stickup_cams"],
        None,
        "bell-ring",
        None,
        None,
    ],
    "wifi_signal_category": [
        "WiFi Signal Category",
        ["chime", "doorbell", "stickup_cams"],
        None,
        "wifi",
        None,
        None,
    ],
    "wifi_signal_strength": [
        "WiFi Signal Strength",
        ["chime", "doorbell", "stickup_cams"],
        "dBm",
        "wifi",
        None,
        "signal_strength",
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a sensor for a Ring device."""
    ring = hass.data[DOMAIN][config_entry.entry_id]
    devices = ring.devices()

    sensors = []
    for device in devices["chimes"]:
        for sensor_type in SENSOR_TYPES:
            if "chime" not in SENSOR_TYPES[sensor_type][1]:
                continue

            sensors.append(RingSensor(hass, config_entry.entry_id, device, sensor_type))

    for device in chain(devices["doorbots"], devices["authorized_doorbots"]):
        for sensor_type in SENSOR_TYPES:
            if "doorbell" not in SENSOR_TYPES[sensor_type][1]:
                continue

            sensors.append(RingSensor(hass, config_entry.entry_id, device, sensor_type))

    for device in devices["stickup_cams"]:
        for sensor_type in SENSOR_TYPES:
            if "stickup_cams" not in SENSOR_TYPES[sensor_type][1]:
                continue

            sensors.append(RingSensor(hass, config_entry.entry_id, device, sensor_type))

    async_add_entities(sensors, True)


class RingSensor(Entity):
    """A sensor implementation for Ring device."""

    def __init__(self, hass, config_entry_id, device, sensor_type):
        """Initialize a sensor for Ring device."""
        super().__init__()
        self._config_entry_id = config_entry_id
        self._sensor_type = sensor_type
        self._device = device
        self._extra = None
        self._icon = "mdi:{}".format(SENSOR_TYPES.get(self._sensor_type)[3])
        self._kind = SENSOR_TYPES.get(self._sensor_type)[4]
        self._name = "{0} {1}".format(
            self._device.name, SENSOR_TYPES.get(self._sensor_type)[0]
        )
        self._state = None
        self._unique_id = f"{self._device.id}-{self._sensor_type}"
        self._disp_disconnect = None
        self._disp_disconnect_health = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._disp_disconnect = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_RING, self._update_callback
        )
        if self._sensor_type not in ("wifi_signal_category", "wifi_signal_strength"):
            return

        self._disp_disconnect_health = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_HEALTH_RING, self._update_callback
        )
        await self.hass.data[DATA_HEALTH_DATA_TRACKER].track_device(
            self._config_entry_id, self._device
        )
        # Write the state, it was not available when doing initial update.
        if self._sensor_type == "wifi_signal_category":
            self._state = self._device.wifi_signal_category

        if self._sensor_type == "wifi_signal_strength":
            self._state = self._device.wifi_signal_strength

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        if self._disp_disconnect:
            self._disp_disconnect()
            self._disp_disconnect = None

        if self._disp_disconnect_health:
            self._disp_disconnect_health()
            self._disp_disconnect_health = None

        if self._sensor_type not in ("wifi_signal_category", "wifi_signal_strength"):
            return

        self.hass.data[DATA_HEALTH_DATA_TRACKER].untrack_device(
            self._config_entry_id, self._device
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_class(self):
        """Return sensor device class."""
        return SENSOR_TYPES[self._sensor_type][5]

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "sw_version": self._device.firmware,
            "name": self._device.name,
            "model": self._device.model,
            "manufacturer": "Ring",
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION

        if self._extra and self._sensor_type.startswith("last_"):
            attrs["created_at"] = self._extra["created_at"]
            attrs["answered"] = self._extra["answered"]
            attrs["recording_status"] = self._extra["recording"]["status"]
            attrs["category"] = self._extra["kind"]

        return attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == "battery" and self._state is not None:
            return icon_for_battery_level(
                battery_level=int(self._state), charging=False
            )
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[2]

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating data from %s sensor", self._name)

        if self._sensor_type == "volume":
            self._state = self._device.volume

        if self._sensor_type == "battery":
            self._state = self._device.battery_life

        if self._sensor_type.startswith("last_"):
            history = self._device.history(limit=1, kind=self._kind, enforce_limit=True)
            if history:
                self._extra = history[0]
                created_at = self._extra["created_at"]
                self._state = created_at.isoformat()

        if self._sensor_type == "wifi_signal_category":
            self._state = self._device.wifi_signal_category

        if self._sensor_type == "wifi_signal_strength":
            self._state = self._device.wifi_signal_strength
