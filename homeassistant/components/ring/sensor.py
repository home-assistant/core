"""This component provides HA sensor support for Ring Door Bell/Chimes."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import (
    ATTRIBUTION,
    DATA_RING_CHIMES,
    DATA_RING_DOORBELLS,
    DATA_RING_STICKUP_CAMS,
    DOMAIN,
    SIGNAL_UPDATE_RING,
)

_LOGGER = logging.getLogger(__name__)

# Sensor types: Name, category, units, icon, kind
SENSOR_TYPES = {
    "battery": ["Battery", ["doorbell", "stickup_cams"], "%", "battery-50", None],
    "last_activity": [
        "Last Activity",
        ["doorbell", "stickup_cams"],
        None,
        "history",
        None,
    ],
    "last_ding": ["Last Ding", ["doorbell"], None, "history", "ding"],
    "last_motion": [
        "Last Motion",
        ["doorbell", "stickup_cams"],
        None,
        "history",
        "motion",
    ],
    "volume": [
        "Volume",
        ["chime", "doorbell", "stickup_cams"],
        None,
        "bell-ring",
        None,
    ],
    "wifi_signal_category": [
        "WiFi Signal Category",
        ["chime", "doorbell", "stickup_cams"],
        None,
        "wifi",
        None,
    ],
    "wifi_signal_strength": [
        "WiFi Signal Strength",
        ["chime", "doorbell", "stickup_cams"],
        "dBm",
        "wifi",
        None,
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a sensor for a Ring device."""
    ring_chimes = hass.data[DATA_RING_CHIMES]
    ring_doorbells = hass.data[DATA_RING_DOORBELLS]
    ring_stickup_cams = hass.data[DATA_RING_STICKUP_CAMS]

    sensors = []
    for device in ring_chimes:
        for sensor_type in SENSOR_TYPES:
            if "chime" not in SENSOR_TYPES[sensor_type][1]:
                continue

            if sensor_type in ("wifi_signal_category", "wifi_signal_strength"):
                await hass.async_add_executor_job(device.update)

            sensors.append(RingSensor(hass, device, sensor_type))

    for device in ring_doorbells:
        for sensor_type in SENSOR_TYPES:
            if "doorbell" not in SENSOR_TYPES[sensor_type][1]:
                continue

            if sensor_type in ("wifi_signal_category", "wifi_signal_strength"):
                await hass.async_add_executor_job(device.update)

            sensors.append(RingSensor(hass, device, sensor_type))

    for device in ring_stickup_cams:
        for sensor_type in SENSOR_TYPES:
            if "stickup_cams" not in SENSOR_TYPES[sensor_type][1]:
                continue

            if sensor_type in ("wifi_signal_category", "wifi_signal_strength"):
                await hass.async_add_executor_job(device.update)

            sensors.append(RingSensor(hass, device, sensor_type))

    async_add_entities(sensors, True)


class RingSensor(Entity):
    """A sensor implementation for Ring device."""

    def __init__(self, hass, data, sensor_type):
        """Initialize a sensor for Ring device."""
        super().__init__()
        self._sensor_type = sensor_type
        self._data = data
        self._extra = None
        self._icon = "mdi:{}".format(SENSOR_TYPES.get(self._sensor_type)[3])
        self._kind = SENSOR_TYPES.get(self._sensor_type)[4]
        self._name = "{0} {1}".format(
            self._data.name, SENSOR_TYPES.get(self._sensor_type)[0]
        )
        self._state = None
        self._tz = str(hass.config.time_zone)
        self._unique_id = f"{self._data.id}-{self._sensor_type}"
        self._disp_disconnect = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._disp_disconnect = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_RING, self._update_callback
        )
        await self.hass.async_add_executor_job(self._data.update)

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        if self._disp_disconnect:
            self._disp_disconnect()
            self._disp_disconnect = None

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
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._data.id)},
            "sw_version": self._data.firmware,
            "name": self._data.name,
            "model": self._data.kind,
            "manufacturer": "Ring",
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
        attrs["timezone"] = self._data.timezone
        attrs["wifi_name"] = self._data.wifi_name

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
            self._state = self._data.volume

        if self._sensor_type == "battery":
            self._state = self._data.battery_life

        if self._sensor_type.startswith("last_"):
            history = self._data.history(
                limit=5, timezone=self._tz, kind=self._kind, enforce_limit=True
            )
            if history:
                self._extra = history[0]
                created_at = self._extra["created_at"]
                self._state = "{0:0>2}:{1:0>2}".format(
                    created_at.hour, created_at.minute
                )

        if self._sensor_type == "wifi_signal_category":
            self._state = self._data.wifi_signal_category

        if self._sensor_type == "wifi_signal_strength":
            self._state = self._data.wifi_signal_strength
