"""Support for RFXtrx sensors."""
import logging

from RFXtrx import SensorEvent

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.const import CONF_SENSORS
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from . import (
    CONF_DATA_TYPE,
    DATA_TYPES,
    DOMAIN,
    SIGNAL_EVENT,
    get_device_id,
    get_rfx_object,
)
from .const import ATTR_EVENT

_LOGGER = logging.getLogger(__name__)


def _battery_convert(value):
    """Battery is given as a value between 0 and 9."""
    if value is None:
        return None
    return value * 10


def _rssi_convert(value):
    """Rssi is given as dBm value."""
    if value is None:
        return None
    return f"{value*8-120}"


DEVICE_CLASSES = {
    "Battery numeric": DEVICE_CLASS_BATTERY,
    "Rssi numeric": DEVICE_CLASS_SIGNAL_STRENGTH,
    "Humidity": DEVICE_CLASS_HUMIDITY,
    "Temperature": DEVICE_CLASS_TEMPERATURE,
}


CONVERT_FUNCTIONS = {
    "Battery numeric": _battery_convert,
    "Rssi numeric": _rssi_convert,
}


async def async_setup_entry(
    hass, config_entry, async_add_entities,
):
    """Set up platform."""
    config = config_entry.data[CONF_SENSORS]
    data_ids = set()

    entities = []
    for packet_id, entity_info in config.items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue

        if entity_info[CONF_DATA_TYPE]:
            data_types = entity_info[CONF_DATA_TYPE]
        else:
            data_types = list(set(event.values) & set(DATA_TYPES))

        device_id = get_device_id(event.device)
        for data_type in data_types:
            data_id = (*device_id, data_type)
            if data_id in data_ids:
                continue
            data_ids.add(data_id)

            entity = RfxtrxSensor(event.device, data_type)
            entities.append(entity)

    async_add_entities(entities)

    @callback
    def sensor_update(event):
        """Handle sensor updates from the RFXtrx gateway."""
        if not isinstance(event, SensorEvent):
            return

        device_id = get_device_id(event.device)
        for data_type in set(event.values) & set(DATA_TYPES):
            data_id = (*device_id, data_type)
            if data_id in data_ids:
                continue
            data_ids.add(data_id)

            _LOGGER.debug(
                "Added sensor (Device ID: %s Class: %s Sub: %s)",
                event.device.id_string.lower(),
                event.device.__class__.__name__,
                event.device.subtype,
            )

            entity = RfxtrxSensor(event.device, data_type, event=event)
            async_add_entities([entity])

    # Subscribe to main RFXtrx events
    hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_EVENT, sensor_update)


class RfxtrxSensor(Entity):
    """Representation of a RFXtrx sensor."""

    def __init__(self, device, data_type, event=None):
        """Initialize the sensor."""
        self.event = None
        self._device = device
        self._name = f"{device.type_string} {device.id_string} {data_type}"
        self.data_type = data_type
        self._unit_of_measurement = DATA_TYPES.get(data_type, "")
        self._device_id = get_device_id(device)
        self._unique_id = "_".join(x for x in (*self._device_id, data_type))

        self._device_class = DEVICE_CLASSES.get(data_type)
        self._convert_fun = CONVERT_FUNCTIONS.get(data_type, lambda x: x)

        if event:
            self._apply_event(event)

    async def async_added_to_hass(self):
        """Restore RFXtrx switch device state (ON/OFF)."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_EVENT, self._handle_event
            )
        )

    def __str__(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.event:
            return None
        value = self.event.values.get(self.data_type)
        return self._convert_fun(value)

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if not self.event:
            return None
        return {ATTR_EVENT: "".join(f"{x:02x}" for x in self.event.data)}

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return a device class for sensor."""
        return self._device_class

    @property
    def unique_id(self):
        """Return unique identifier of remote device."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, *self._device_id)},
            "name": f"{self._device.type_string} {self._device.id_string}",
            "model": self._device.type_string,
        }

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
        self.event = event

    @callback
    def _handle_event(self, event):
        """Check if event applies to me and update."""
        if not isinstance(event, SensorEvent):
            return

        if event.device.id_string != self._device.id_string:
            return

        if self.data_type not in event.values:
            return

        _LOGGER.debug(
            "Sensor update (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string,
            event.device.__class__.__name__,
            event.device.subtype,
        )

        self._apply_event(event)

        self.async_write_ha_state()
