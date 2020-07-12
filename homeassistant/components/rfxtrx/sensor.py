"""Support for RFXtrx sensors."""
import logging

from RFXtrx import ControlEvent, SensorEvent

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_DEVICES
from homeassistant.helpers.entity import Entity

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_FIRE_EVENT,
    DATA_TYPES,
    SIGNAL_EVENT,
    get_device_id,
    get_rfx_object,
)

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RFXtrx platform."""
    if discovery_info is None:
        return

    data_ids = set()

    def supported(event):
        return isinstance(event, (ControlEvent, SensorEvent))

    entities = []
    for packet_id, entity_info in discovery_info[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        if not supported(event):
            continue

        device_id = get_device_id(event.device)
        for data_type in set(event.values) & set(DATA_TYPES):
            data_id = (*device_id, data_type)
            if data_id in data_ids:
                continue
            data_ids.add(data_id)

            entity = RfxtrxSensor(
                event.device, data_type, entity_info[CONF_FIRE_EVENT],
            )
            entities.append(entity)

    add_entities(entities)

    def sensor_update(event):
        """Handle sensor updates from the RFXtrx gateway."""
        if not supported(event):
            return

        device_id = get_device_id(event.device)
        for data_type in set(event.values) & set(DATA_TYPES):
            data_id = (*device_id, data_type)
            if data_id in data_ids:
                continue
            data_ids.add(data_id)

            _LOGGER.info(
                "Added sensor (Device ID: %s Class: %s Sub: %s, Event: %s)",
                event.device.id_string.lower(),
                event.device.__class__.__name__,
                event.device.subtype,
                "".join(f"{x:02x}" for x in event.data),
            )

            entity = RfxtrxSensor(event.device, data_type, event=event)
            add_entities([entity])

    # Subscribe to main RFXtrx events
    if discovery_info[CONF_AUTOMATIC_ADD]:
        hass.helpers.dispatcher.dispatcher_connect(SIGNAL_EVENT, sensor_update)


class RfxtrxSensor(Entity):
    """Representation of a RFXtrx sensor."""

    def __init__(self, device, data_type, should_fire_event=False, event=None):
        """Initialize the sensor."""
        self.event = None
        self._device = device
        self._name = f"{device.type_string} {device.id_string} {data_type}"
        self.should_fire_event = should_fire_event
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
        return self.event.values

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

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
        self.event = event

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

        self.schedule_update_ha_state()
        if self.should_fire_event:
            self.hass.bus.fire("signal_received", {ATTR_ENTITY_ID: self.entity_id})
