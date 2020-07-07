"""Support for RFXtrx sensors."""
import logging

from RFXtrx import SensorEvent
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from . import (
    ATTR_DATA_TYPE,
    ATTR_FIRE_EVENT,
    CONF_AUTOMATIC_ADD,
    CONF_DATA_TYPE,
    CONF_DEVICES,
    CONF_FIRE_EVENT,
    DATA_TYPES,
    RFX_DEVICES,
    SIGNAL_EVENT,
    get_rfx_object,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
                    vol.Optional(CONF_DATA_TYPE, default=[]): vol.All(
                        cv.ensure_list, [vol.In(DATA_TYPES.keys())]
                    ),
                }
            )
        },
        vol.Optional(CONF_AUTOMATIC_ADD, default=False): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RFXtrx platform."""
    sensors = []
    for packet_id, entity_info in config[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        device_id = "sensor_{}".format(slugify(event.device.id_string.lower()))
        if device_id in RFX_DEVICES:
            continue
        _LOGGER.info("Add %s rfxtrx.sensor", entity_info[ATTR_NAME])

        sub_sensors = {}
        data_types = entity_info[ATTR_DATA_TYPE]
        if not data_types:
            data_types = [""]
            for data_type in DATA_TYPES:
                if data_type in event.values:
                    data_types = [data_type]
                    break
        for _data_type in data_types:
            new_sensor = RfxtrxSensor(
                None,
                event.device,
                entity_info[ATTR_NAME],
                _data_type,
                entity_info[ATTR_FIRE_EVENT],
            )
            sensors.append(new_sensor)
            sub_sensors[_data_type] = new_sensor
        RFX_DEVICES[device_id] = sub_sensors
    add_entities(sensors)

    def sensor_update(event):
        """Handle sensor updates from the RFXtrx gateway."""
        if not isinstance(event, SensorEvent):
            return

        device_id = f"sensor_{slugify(event.device.id_string.lower())}"

        if device_id in RFX_DEVICES:
            return

        # Add entity if not exist and the automatic_add is True
        if not config[CONF_AUTOMATIC_ADD]:
            return

        pkt_id = "".join(f"{x:02x}" for x in event.data)
        _LOGGER.info("Automatic add rfxtrx.sensor: %s", pkt_id)

        data_type = ""
        for _data_type in DATA_TYPES:
            if _data_type in event.values:
                data_type = _data_type
                break
        new_sensor = RfxtrxSensor(event, event.device, pkt_id, data_type)
        new_sensor.apply_event(event)
        sub_sensors = {}
        sub_sensors[new_sensor.data_type] = new_sensor
        RFX_DEVICES[device_id] = sub_sensors
        add_entities([new_sensor])

    # Subscribe to main RFXtrx events
    hass.helpers.dispatcher.dispatcher_connect(SIGNAL_EVENT, sensor_update)


class RfxtrxSensor(Entity):
    """Representation of a RFXtrx sensor."""

    def __init__(self, event, device, name, data_type, should_fire_event=False):
        """Initialize the sensor."""
        self.event = event
        self._device = device
        self._name = name
        self.should_fire_event = should_fire_event
        self.data_type = data_type
        self._unit_of_measurement = DATA_TYPES.get(data_type, "")
        self._unique_id = (
            f"{device.packettype:x}_{device.subtype:x}_{device.id_string}_{data_type}"
        )

    async def async_added_to_hass(self):
        """Restore RFXtrx switch device state (ON/OFF)."""
        await super().async_added_to_hass()

        def _handle_event(event):
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

            self.apply_event(event)

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_EVENT, _handle_event
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
        return self.event.values.get(self.data_type)

    @property
    def name(self):
        """Get the name of the sensor."""
        return f"{self._name} {self.data_type}"

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
    def unique_id(self):
        """Return unique identifier of remote device."""
        return self._unique_id

    def apply_event(self, event):
        """Apply command from rfxtrx."""
        self.event = event
        if self.hass:
            self.schedule_update_ha_state()
            if self.should_fire_event:
                self.hass.bus.fire("signal_received", {ATTR_ENTITY_ID: self.entity_id})
