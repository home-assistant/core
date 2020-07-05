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
    CONF_NAME,
)
from homeassistant.helpers import config_validation as cv, event as evt
from homeassistant.util import dt as dt_util, slugify

from . import (
    ATTR_NAME,
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_DEVICES,
    CONF_FIRE_EVENT,
    CONF_OFF_DELAY,
    RECEIVED_EVT_SUBSCRIBERS,
    RFX_DEVICES,
    apply_received_command,
    find_possible_pt2262_device,
    get_pt2262_cmd,
    get_pt2262_device,
    get_pt2262_deviceid,
    get_rfx_object,
)

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Binary Sensor platform to RFXtrx."""
    sensors = []

    for packet_id, entity in config[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        device_id = slugify(event.device.id_string.lower())

        if device_id in RFX_DEVICES:
            continue

        if entity.get(CONF_DATA_BITS) is not None:
            _LOGGER.debug(
                "Masked device id: %s",
                get_pt2262_deviceid(device_id, entity.get(CONF_DATA_BITS)),
            )

        _LOGGER.debug(
            "Add %s rfxtrx.binary_sensor (class %s)",
            entity[ATTR_NAME],
            entity.get(CONF_DEVICE_CLASS),
        )

        device = RfxtrxBinarySensor(
            event,
            entity.get(CONF_NAME),
            entity.get(CONF_DEVICE_CLASS),
            entity[CONF_FIRE_EVENT],
            entity.get(CONF_OFF_DELAY),
            entity.get(CONF_DATA_BITS),
            entity.get(CONF_COMMAND_ON),
            entity.get(CONF_COMMAND_OFF),
        )
        sensors.append(device)
        RFX_DEVICES[device_id] = device

    add_entities(sensors)

    def binary_sensor_update(event):
        """Call for control updates from the RFXtrx gateway."""
        if not isinstance(event, rfxtrxmod.ControlEvent):
            return

        device_id = slugify(event.device.id_string.lower())

        sensor = RFX_DEVICES.get(device_id, get_pt2262_device(device_id))

        if sensor is None:
            # Add the entity if not exists and automatic_add is True
            if not config[CONF_AUTOMATIC_ADD]:
                return

            if event.device.packettype == 0x13:
                poss_dev = find_possible_pt2262_device(device_id)
                if poss_dev is not None:
                    poss_id = slugify(poss_dev.event.device.id_string.lower())
                    _LOGGER.debug("Found possible matching device ID: %s", poss_id)

            pkt_id = "".join(f"{x:02x}" for x in event.data)
            sensor = RfxtrxBinarySensor(event, pkt_id)
            RFX_DEVICES[device_id] = sensor
            add_entities([sensor])
            _LOGGER.info(
                "Added binary sensor %s (Device ID: %s Class: %s Sub: %s)",
                pkt_id,
                slugify(event.device.id_string.lower()),
                event.device.__class__.__name__,
                event.device.subtype,
            )

        elif not isinstance(sensor, RfxtrxBinarySensor):
            return
        else:
            _LOGGER.debug(
                "Binary sensor update (Device ID: %s Class: %s Sub: %s)",
                slugify(event.device.id_string.lower()),
                event.device.__class__.__name__,
                event.device.subtype,
            )

        if sensor.is_lighting4:
            if sensor.data_bits is not None:
                cmd = get_pt2262_cmd(device_id, sensor.data_bits)
                sensor.apply_cmd(int(cmd, 16))
            else:
                sensor.update_state(True)
        else:
            apply_received_command(event)

        if (
            sensor.is_on
            and sensor.off_delay is not None
            and sensor.delay_listener is None
        ):

            def off_delay_listener(now):
                """Switch device off after a delay."""
                sensor.delay_listener = None
                sensor.update_state(False)

            sensor.delay_listener = evt.track_point_in_time(
                hass, off_delay_listener, dt_util.utcnow() + sensor.off_delay
            )

    # Subscribe to main RFXtrx events
    if binary_sensor_update not in RECEIVED_EVT_SUBSCRIBERS:
        RECEIVED_EVT_SUBSCRIBERS.append(binary_sensor_update)


class RfxtrxBinarySensor(BinarySensorEntity):
    """A representation of a RFXtrx binary sensor."""

    def __init__(
        self,
        event,
        name,
        device_class=None,
        should_fire=False,
        off_delay=None,
        data_bits=None,
        cmd_on=None,
        cmd_off=None,
    ):
        """Initialize the RFXtrx sensor."""
        self.event = event
        self._name = name
        self._should_fire_event = should_fire
        self._device_class = device_class
        self._off_delay = off_delay
        self._state = False
        self.is_lighting4 = event.device.packettype == 0x13
        self.delay_listener = None
        self._data_bits = data_bits
        self._cmd_on = cmd_on
        self._cmd_off = cmd_off
        self._unique_id = f"{slugify(self.event.device.type_string.lower())}_{slugify(self.event.device.id_string.lower())}"

        if data_bits is not None:
            self._masked_id = get_pt2262_deviceid(
                event.device.id_string.lower(), data_bits
            )
        else:
            self._masked_id = None

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def masked_id(self):
        """Return the masked device id (isolated address bits)."""
        return self._masked_id

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

    def apply_cmd(self, cmd):
        """Apply a command for updating the state."""
        if cmd == self.cmd_on:
            self.update_state(True)
        elif cmd == self.cmd_off:
            self.update_state(False)

    def update_state(self, state):
        """Update the state of the device."""
        self._state = state
        if self.hass:
            self.schedule_update_ha_state()
