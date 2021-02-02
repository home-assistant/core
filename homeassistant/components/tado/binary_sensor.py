"""Support for Tado sensors for each zone."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DATA,
    DOMAIN,
    SIGNAL_TADO_UPDATE_RECEIVED,
    TYPE_AIR_CONDITIONING,
    TYPE_BATTERY,
    TYPE_HEATING,
    TYPE_HOT_WATER,
    TYPE_POWER,
)
from .entity import TadoDeviceEntity, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)

DEVICE_SENSORS = {
    TYPE_BATTERY: [
        "battery state",
        "connection state",
    ],
    TYPE_POWER: [
        "connection state",
    ],
}

ZONE_SENSORS = {
    TYPE_HEATING: [
        "power",
        "link",
        "overlay",
        "early start",
        "open window",
    ],
    TYPE_AIR_CONDITIONING: [
        "power",
        "link",
        "overlay",
        "open window",
    ],
    TYPE_HOT_WATER: ["power", "link", "overlay"],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Tado sensor platform."""

    tado = hass.data[DOMAIN][entry.entry_id][DATA]
    devices = tado.devices
    zones = tado.zones
    entities = []

    # Create device sensors
    for device in devices:
        if "batteryState" in device:
            device_type = TYPE_BATTERY
        else:
            device_type = TYPE_POWER

        entities.extend(
            [
                TadoDeviceBinarySensor(tado, device, variable)
                for variable in DEVICE_SENSORS[device_type]
            ]
        )

    # Create zone sensors
    for zone in zones:
        zone_type = zone["type"]
        if zone_type not in ZONE_SENSORS:
            _LOGGER.warning("Unknown zone type skipped: %s", zone_type)
            continue

        entities.extend(
            [
                TadoZoneBinarySensor(tado, zone["name"], zone["id"], variable)
                for variable in ZONE_SENSORS[zone_type]
            ]
        )

    if entities:
        async_add_entities(entities, True)


class TadoDeviceBinarySensor(TadoDeviceEntity, BinarySensorEntity):
    """Representation of a tado Sensor."""

    def __init__(self, tado, device_info, device_variable):
        """Initialize of the Tado Sensor."""
        self._tado = tado
        super().__init__(device_info)

        self.device_variable = device_variable

        self._unique_id = f"{device_variable} {self.device_id} {tado.home_id}"

        self._state = None

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "device", self.device_id
                ),
                self._async_update_callback,
            )
        )
        self._async_update_device_data()

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.device_name} {self.device_variable}"

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        if self.device_variable == "battery state":
            return DEVICE_CLASS_BATTERY
        if self.device_variable == "connection state":
            return DEVICE_CLASS_CONNECTIVITY
        return None

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_device_data()
        self.async_write_ha_state()

    @callback
    def _async_update_device_data(self):
        """Handle update callbacks."""
        try:
            self._device_info = self._tado.data["device"][self.device_id]
        except KeyError:
            return

        if self.device_variable == "battery state":
            self._state = self._device_info["batteryState"] == "LOW"
        elif self.device_variable == "connection state":
            self._state = self._device_info.get("connectionState", {}).get(
                "value", False
            )


class TadoZoneBinarySensor(TadoZoneEntity, BinarySensorEntity):
    """Representation of a tado Sensor."""

    def __init__(self, tado, zone_name, zone_id, zone_variable):
        """Initialize of the Tado Sensor."""
        self._tado = tado
        super().__init__(zone_name, tado.home_id, zone_id)

        self.zone_variable = zone_variable

        self._unique_id = f"{zone_variable} {zone_id} {tado.home_id}"

        self._state = None
        self._tado_zone_data = None

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "zone", self.zone_id
                ),
                self._async_update_callback,
            )
        )
        self._async_update_zone_data()

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.zone_name} {self.zone_variable}"

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        if self.zone_variable == "early start":
            return DEVICE_CLASS_POWER
        if self.zone_variable == "link":
            return DEVICE_CLASS_CONNECTIVITY
        if self.zone_variable == "open window":
            return DEVICE_CLASS_WINDOW
        if self.zone_variable == "overlay":
            return DEVICE_CLASS_POWER
        if self.zone_variable == "power":
            return DEVICE_CLASS_POWER
        return None

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_zone_data()
        self.async_write_ha_state()

    @callback
    def _async_update_zone_data(self):
        """Handle update callbacks."""
        try:
            self._tado_zone_data = self._tado.data["zone"][self.zone_id]
        except KeyError:
            return

        if self.zone_variable == "power":
            self._state = self._tado_zone_data.power

        elif self.zone_variable == "link":
            self._state = self._tado_zone_data.link

        elif self.zone_variable == "overlay":
            self._state = self._tado_zone_data.overlay_active

        elif self.zone_variable == "early start":
            self._state = self._tado_zone_data.preparation

        elif self.zone_variable == "open window":
            self._state = bool(
                self._tado_zone_data.open_window
                or self._tado_zone_data.open_window_detected
            )
