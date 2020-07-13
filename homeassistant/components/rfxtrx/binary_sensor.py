"""Support for RFXtrx binary sensors."""
import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_DEVICES,
)
from homeassistant.core import callback
from homeassistant.helpers import event as evt

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_OFF_DELAY,
    DOMAIN,
    SIGNAL_EVENT,
    find_possible_pt2262_device,
    get_device_id,
    get_pt2262_cmd,
    get_rfx_object,
)
from .const import (
    COMMAND_OFF_LIST,
    COMMAND_ON_LIST,
    DATA_RFXTRX_CONFIG,
    DEVICE_PACKET_TYPE_LIGHTING4,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities,
):
    """Set up platform."""
    sensors = []

    device_ids = set()
    pt2262_devices = []

    discovery_info = hass.data[DATA_RFXTRX_CONFIG]

    def supported(event):
        return isinstance(event, rfxtrxmod.ControlEvent)

    for packet_id, entity in discovery_info[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        if not supported(event):
            return

        device_id = get_device_id(event.device, data_bits=entity.get(CONF_DATA_BITS))
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        if event.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            find_possible_pt2262_device(pt2262_devices, event.device.id_string)
            pt2262_devices.append(event.device.id_string)

        device = RfxtrxBinarySensor(
            event.device,
            device_id,
            entity.get(CONF_DEVICE_CLASS),
            entity.get(CONF_OFF_DELAY),
            entity.get(CONF_DATA_BITS),
            entity.get(CONF_COMMAND_ON),
            entity.get(CONF_COMMAND_OFF),
        )
        sensors.append(device)

    async_add_entities(sensors)

    @callback
    def binary_sensor_update(event, device_id):
        """Call for control updates from the RFXtrx gateway."""
        if not supported(event):
            return

        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added binary sensor (Device ID: %s Class: %s Sub: %s Event: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
            "".join(f"{x:02x}" for x in event.data),
        )
        sensor = RfxtrxBinarySensor(event.device, device_id, event=event)
        async_add_entities([sensor])

    # Subscribe to main RFXtrx events
    if discovery_info[CONF_AUTOMATIC_ADD]:
        hass.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_EVENT, binary_sensor_update
        )


class RfxtrxBinarySensor(BinarySensorEntity):
    """A representation of a RFXtrx binary sensor."""

    def __init__(
        self,
        device,
        device_id,
        device_class=None,
        off_delay=None,
        data_bits=None,
        cmd_on=None,
        cmd_off=None,
        event=None,
    ):
        """Initialize the RFXtrx sensor."""
        self.event = None
        self._device = device
        self._name = f"{device.type_string} {device.id_string}"
        self._device_class = device_class
        self._data_bits = data_bits
        self._off_delay = off_delay
        self._state = False
        self.delay_listener = None
        self._cmd_on = cmd_on
        self._cmd_off = cmd_off

        self._device_id = device_id
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

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, *self._device_id)},
            "name": f"{self._device.type_string} {self._device.id_string}",
            "model": self._device.type_string,
        }

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

    @callback
    def _handle_event(self, event, device_id):
        """Check if event applies to me and update."""
        if device_id != self._device_id:
            return

        _LOGGER.debug(
            "Binary sensor update (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string,
            event.device.__class__.__name__,
            event.device.subtype,
        )

        self._apply_event(event)

        self.async_write_ha_state()

        if self.is_on and self.off_delay is not None and self.delay_listener is None:

            @callback
            def off_delay_listener(now):
                """Switch device off after a delay."""
                self.delay_listener = None
                self._state = False
                self.async_write_ha_state()

            self.delay_listener = evt.async_call_later(
                self.hass, self.off_delay.total_seconds(), off_delay_listener
            )
