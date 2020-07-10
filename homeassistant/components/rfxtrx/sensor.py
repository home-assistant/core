"""Support for RFXtrx sensors."""
import logging

from RFXtrx import SensorEvent
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ENTITY_ID, CONF_DEVICES, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_TYPE,
    CONF_FIRE_EVENT,
    DATA_TYPES,
    SIGNAL_EVENT,
    get_device_id,
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
    data_ids = set()

    entities = []
    for packet_id, entity_info in config[CONF_DEVICES].items():
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

            entity = RfxtrxSensor(
                event.device,
                entity_info[CONF_NAME],
                data_type,
                entity_info[CONF_FIRE_EVENT],
            )
            entities.append(entity)

    add_entities(entities)

    def sensor_update(event):
        """Handle sensor updates from the RFXtrx gateway."""
        if not isinstance(event, SensorEvent):
            return

        pkt_id = "".join(f"{x:02x}" for x in event.data)
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

            entity = RfxtrxSensor(event.device, pkt_id, data_type, event=event)
            add_entities([entity])

    # Subscribe to main RFXtrx events
    if config[CONF_AUTOMATIC_ADD]:
        hass.helpers.dispatcher.dispatcher_connect(SIGNAL_EVENT, sensor_update)


class RfxtrxSensor(Entity):
    """Representation of a RFXtrx sensor."""

    def __init__(self, device, name, data_type, should_fire_event=False, event=None):
        """Initialize the sensor."""
        self.event = None
        self._device = device
        self._name = name
        self.should_fire_event = should_fire_event
        self.data_type = data_type
        self._unit_of_measurement = DATA_TYPES.get(data_type, "")
        self._device_id = get_device_id(device)
        self._unique_id = "_".join(x for x in (*self._device_id, data_type))

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
