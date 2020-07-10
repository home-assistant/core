"""Support for RFXtrx binary sensors."""
import logging

import RFXtrx as rfxtrxmod
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_DEVICES,
    CONF_NAME,
)
from homeassistant.helpers import config_validation as cv, event as evt

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_FIRE_EVENT,
    CONF_OFF_DELAY,
    SIGNAL_EVENT,
    find_possible_pt2262_device,
    fire_command_event,
    get_device_id,
    get_pt2262_cmd,
    get_pt2262_deviceid,
    get_rfx_object,
)
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST, DEVICE_PACKET_TYPE_LIGHTING4

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                    vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
                    vol.Optional(CONF_OFF_DELAY): vol.Any(
                        cv.time_period, cv.positive_timedelta
                    ),
                    vol.Optional(CONF_DATA_BITS): cv.positive_int,
                    vol.Optional(CONF_COMMAND_ON): cv.byte,
                    vol.Optional(CONF_COMMAND_OFF): cv.byte,
                }
            )
        },
        vol.Optional(CONF_AUTOMATIC_ADD, default=False): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)


def _get_device_data_bits(device, device_bits):
    """Deduce data bits for device based on a cache of device bits."""
    data_bits = None
    if device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
        for id_masked, bits in device_bits.items():
            if get_pt2262_deviceid(device.id_string, bits) == id_masked:
                data_bits = bits
                break
    return data_bits


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Binary Sensor platform to RFXtrx."""
    sensors = []

    device_ids = set()
    device_bits = {}

    pt2262_devices = []

    for packet_id, entity in config[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue

        device_id = get_device_id(event.device, data_bits=entity.get(CONF_DATA_BITS))
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        if event.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            find_possible_pt2262_device(pt2262_devices, event.device.id_string)
            pt2262_devices.append(event.device.id_string)

        device = RfxtrxBinarySensor(
            event.device,
            entity.get(CONF_NAME),
            entity.get(CONF_DEVICE_CLASS),
            entity[CONF_FIRE_EVENT],
            entity.get(CONF_OFF_DELAY),
            entity.get(CONF_DATA_BITS),
            entity.get(CONF_COMMAND_ON),
            entity.get(CONF_COMMAND_OFF),
        )
        sensors.append(device)

    add_entities(sensors)

    def binary_sensor_update(event):
        """Call for control updates from the RFXtrx gateway."""
        if not isinstance(event, rfxtrxmod.ControlEvent):
            return

        data_bits = _get_device_data_bits(event.device, device_bits)

        device_id = get_device_id(event.device, data_bits=data_bits)
        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added binary sensor (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
        )
        pkt_id = "".join(f"{x:02x}" for x in event.data)
        sensor = RfxtrxBinarySensor(
            event.device, pkt_id, data_bits=data_bits, event=event
        )
        add_entities([sensor])

    # Subscribe to main RFXtrx events
    if config[CONF_AUTOMATIC_ADD]:
        hass.helpers.dispatcher.dispatcher_connect(SIGNAL_EVENT, binary_sensor_update)


class RfxtrxBinarySensor(BinarySensorEntity):
    """A representation of a RFXtrx binary sensor."""

    def __init__(
        self,
        device,
        name,
        device_class=None,
        should_fire=False,
        off_delay=None,
        data_bits=None,
        cmd_on=None,
        cmd_off=None,
        event=None,
    ):
        """Initialize the RFXtrx sensor."""
        self.event = None
        self._device = device
        self._name = name
        self._should_fire_event = should_fire
        self._device_class = device_class
        self._off_delay = off_delay
        self._state = False
        self.delay_listener = None
        self._data_bits = data_bits
        self._cmd_on = cmd_on
        self._cmd_off = cmd_off

        self._device_id = get_device_id(device, data_bits=data_bits)
        self._unique_id = "_".join(x for x in self._device_id)

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

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def data_bits(self):
        """Return the number of data bits."""
        return self._data_bits

    @property
    def cmd_on(self):
        """Return the value of the 'On' command."""
        return self._cmd_on

    @property
    def cmd_off(self):
        """Return the value of the 'Off' command."""
        return self._cmd_off

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def should_fire_event(self):
        """Return is the device must fire event."""
        return self._should_fire_event

    @property
    def device_class(self):
        """Return the sensor class."""
        return self._device_class

    @property
    def off_delay(self):
        """Return the off_delay attribute value."""
        return self._off_delay

    @property
    def is_on(self):
        """Return true if the sensor state is True."""
        return self._state

    @property
    def unique_id(self):
        """Return unique identifier of remote device."""
        return self._unique_id

    def _apply_event_lighting4(self, event):
        """Apply event for a lighting 4 device."""
        if self.data_bits is not None:
            cmd = get_pt2262_cmd(event.device.id_string, self.data_bits)
            cmd = int(cmd, 16)
            if cmd == self.cmd_on:
                self._state = True
            elif cmd == self.cmd_off:
                self._state = False
        else:
            self._state = True

    def _apply_event_standard(self, event):
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
        if event.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            self._apply_event_lighting4(event)
        else:
            self._apply_event_standard(event)

    def _handle_event(self, event):
        """Check if event applies to me and update."""
        if get_device_id(event.device, data_bits=self._data_bits) != self._device_id:
            return

        _LOGGER.debug(
            "Binary sensor update (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string,
            event.device.__class__.__name__,
            event.device.subtype,
        )

        self._apply_event(event)

        self.schedule_update_ha_state()
        if self.should_fire_event:
            fire_command_event(self.hass, self.entity_id, event.values["Command"])

        if self.is_on and self.off_delay is not None and self.delay_listener is None:

            def off_delay_listener(now):
                """Switch device off after a delay."""
                self.delay_listener = None
                self._state = False
                self.schedule_update_ha_state()

            self.delay_listener = evt.call_later(
                self.hass, self.off_delay.total_seconds(), off_delay_listener
            )
