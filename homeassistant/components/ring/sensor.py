"""This component provides HA sensor support for Ring Door Bell/Chimes."""
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import DOMAIN
from .entity import RingEntityMixin


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a sensor for a Ring device."""
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]

    sensors = []

    for device_type in ("chimes", "doorbots", "authorized_doorbots", "stickup_cams"):
        for sensor_type in SENSOR_TYPES:
            if device_type not in SENSOR_TYPES[sensor_type][1]:
                continue

            for device in devices[device_type]:
                if device_type == "battery" and device.battery_life is None:
                    continue

                sensors.append(
                    SENSOR_TYPES[sensor_type][6](
                        config_entry.entry_id, device, sensor_type
                    )
                )

    async_add_entities(sensors)


class RingSensor(RingEntityMixin, Entity):
    """A sensor implementation for Ring device."""

    def __init__(self, config_entry_id, device, sensor_type):
        """Initialize a sensor for Ring device."""
        super().__init__(config_entry_id, device)
        self._sensor_type = sensor_type
        self._extra = None
        self._icon = "mdi:{}".format(SENSOR_TYPES.get(sensor_type)[3])
        self._kind = SENSOR_TYPES.get(sensor_type)[4]
        self._name = "{} {}".format(self._device.name, SENSOR_TYPES.get(sensor_type)[0])
        self._unique_id = f"{device.id}-{sensor_type}"

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
        if self._sensor_type == "volume":
            return self._device.volume

        if self._sensor_type == "battery":
            return self._device.battery_life

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_class(self):
        """Return sensor device class."""
        return SENSOR_TYPES[self._sensor_type][5]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == "battery" and self._device.battery_life is not None:
            return icon_for_battery_level(
                battery_level=self._device.battery_life, charging=False
            )
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[2]


class HealthDataRingSensor(RingSensor):
    """Ring sensor that relies on health data."""

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()

        await self.ring_objects["health_data"].async_track_device(
            self._device, self._health_update_callback
        )

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        await super().async_will_remove_from_hass()

        self.ring_objects["health_data"].async_untrack_device(
            self._device, self._health_update_callback
        )

    @callback
    def _health_update_callback(self, _health_data):
        """Call update method."""
        self.async_write_ha_state()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # These sensors are data hungry and not useful. Disable by default.
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_type == "wifi_signal_category":
            return self._device.wifi_signal_category

        if self._sensor_type == "wifi_signal_strength":
            return self._device.wifi_signal_strength


class HistoryRingSensor(RingSensor):
    """Ring sensor that relies on history data."""

    _latest_event = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()

        await self.ring_objects["history_data"].async_track_device(
            self._device, self._history_update_callback
        )

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        await super().async_will_remove_from_hass()

        self.ring_objects["history_data"].async_untrack_device(
            self._device, self._history_update_callback
        )

    @callback
    def _history_update_callback(self, history_data):
        """Call update method."""
        if not history_data:
            return

        found = None
        if self._kind is None:
            found = history_data[0]
        else:
            for entry in history_data:
                if entry["kind"] == self._kind:
                    found = entry
                    break

        if not found:
            return

        self._latest_event = found
        self.async_write_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._latest_event is None:
            return None

        return self._latest_event["created_at"].isoformat()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = super().device_state_attributes

        if self._latest_event:
            attrs["created_at"] = self._latest_event["created_at"]
            attrs["answered"] = self._latest_event["answered"]
            attrs["recording_status"] = self._latest_event["recording"]["status"]
            attrs["category"] = self._latest_event["kind"]

        return attrs


# Sensor types: Name, category, units, icon, kind, device_class, class
SENSOR_TYPES = {
    "battery": [
        "Battery",
        ["doorbots", "authorized_doorbots", "stickup_cams"],
        PERCENTAGE,
        None,
        None,
        "battery",
        RingSensor,
    ],
    "last_activity": [
        "Last Activity",
        ["doorbots", "authorized_doorbots", "stickup_cams"],
        None,
        "history",
        None,
        "timestamp",
        HistoryRingSensor,
    ],
    "last_ding": [
        "Last Ding",
        ["doorbots", "authorized_doorbots"],
        None,
        "history",
        "ding",
        "timestamp",
        HistoryRingSensor,
    ],
    "last_motion": [
        "Last Motion",
        ["doorbots", "authorized_doorbots", "stickup_cams"],
        None,
        "history",
        "motion",
        "timestamp",
        HistoryRingSensor,
    ],
    "volume": [
        "Volume",
        ["chimes", "doorbots", "authorized_doorbots", "stickup_cams"],
        None,
        "bell-ring",
        None,
        None,
        RingSensor,
    ],
    "wifi_signal_category": [
        "WiFi Signal Category",
        ["chimes", "doorbots", "authorized_doorbots", "stickup_cams"],
        None,
        "wifi",
        None,
        None,
        HealthDataRingSensor,
    ],
    "wifi_signal_strength": [
        "WiFi Signal Strength",
        ["chimes", "doorbots", "authorized_doorbots", "stickup_cams"],
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        "wifi",
        None,
        "signal_strength",
        HealthDataRingSensor,
    ],
}
