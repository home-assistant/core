"""Support for DSMR Reader through MQTT."""
import logging

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt, slugify

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dsmr_reader"
ATTR_UPDATED = "updated"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up DSMR Reader sensors."""
    async_add_entities(
        [
            DSMRSensor("dsmr/reading/electricity_delivered_1", "kWh"),
            DSMRSensor("dsmr/reading/electricity_returned_1", "kWh"),
            DSMRSensor("dsmr/reading/electricity_delivered_2", "kWh"),
            DSMRSensor("dsmr/reading/electricity_returned_2", "kWh"),
            DSMRSensor("dsmr/reading/electricity_currently_delivered", "kW"),
            DSMRSensor("dsmr/reading/electricity_currently_returned", "kW"),
            DSMRSensor("dsmr/reading/phase_currently_delivered_l1", "kW"),
            DSMRSensor("dsmr/reading/phase_currently_delivered_l2", "kW"),
            DSMRSensor("dsmr/reading/phase_currently_delivered_l3", "kW"),
            DSMRSensor("dsmr/reading/phase_currently_returned_l1", "kW"),
            DSMRSensor("dsmr/reading/phase_currently_returned_l2", "kW"),
            DSMRSensor("dsmr/reading/phase_currently_returned_l3", "kW"),
            DSMRSensor("dsmr/reading/extra_device_delivered", "m3"),
            DSMRSensor("dsmr/reading/phase_voltage_l1", "V"),
            DSMRSensor("dsmr/reading/phase_voltage_l2", "V"),
            DSMRSensor("dsmr/reading/phase_voltage_l3", "V"),
            DSMRSensor("dsmr/consumption/gas/delivered", "m3"),
            DSMRSensor("dsmr/consumption/gas/currently_delivered", "m3"),
            DSMRSensor("dsmr/consumption/gas/read_at", ""),
            DSMRSensor("dsmr/day-consumption/electricity1", "kWh"),
            DSMRSensor("dsmr/day-consumption/electricity2", "kWh"),
            DSMRSensor("dsmr/day-consumption/electricity1_returned", "kWh"),
            DSMRSensor("dsmr/day-consumption/electricity2_returned", "kWh"),
            DSMRSensor("dsmr/day-consumption/electricity_merged", "kWh"),
            DSMRSensor("dsmr/day-consumption/electricity_returned_merged", "kWh"),
            DSMRSensor("dsmr/day-consumption/electricity1_cost", "€"),
            DSMRSensor("dsmr/day-consumption/electricity2_cost", "€"),
            DSMRSensor("dsmr/day-consumption/electricity_cost_merged", "€"),
            DSMRSensor("dsmr/day-consumption/gas", "m3"),
            DSMRSensor("dsmr/day-consumption/gas_cost", "€"),
            DSMRSensor("dsmr/day-consumption/total_cost", "€"),
        ]
    )


class DSMRSensor(Entity):
    """Representation of a DSMR sensor that is updated via MQTT."""

    def __init__(self, state_topic, unit_of_measurement):
        """Initialize the sensor."""

        self._name = ""
        self._main_topic = ""

        parts = state_topic.split("/")
        if len(parts) != 3 and len(parts) != 4:
            _LOGGER.error("Topic expected to have 3 or 4 parts: %", state_topic)
            self._main_topic = "unknown"
            self._name = state_topic
        else:
            self._main_topic = parts[1]
            if len(parts) == 3:
                self._name = parts[2]
            else:
                self._name = f"{parts[2]}_{parts[3]}"

        self._state = 0
        self._state_topic = state_topic
        self._device_id = slugify(self._name).upper()
        self._updated = dt.utcnow()
        self._unit_of_measurement = unit_of_measurement

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""

        @callback
        def update_state(value):
            """Update the sensor state."""
            self._state = value
            self._updated = dt.utcnow()
            self.async_schedule_update_ha_state()

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            update_state(msg.payload)

        return await mqtt.async_subscribe(
            self.hass, self._state_topic, message_received, 1
        )

    @property
    def name(self):
        """Return the name of the sensor supplied in constructor."""
        return f"{self._main_topic}_{self._name}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_UPDATED: self._updated}

    @property
    def state(self):
        """Return the current state of the entity."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of this sensor."""
        return self._unit_of_measurement
