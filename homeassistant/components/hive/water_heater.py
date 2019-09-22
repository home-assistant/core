"""Support for hive water heaters."""
import logging

import voluptuous as vol

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_OFF,
    STATE_ON,
    SUPPORT_OPERATION_MODE,
    WaterHeaterDevice,
)
from homeassistant.const import ATTR_ENTITY_ID, TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv

from . import DATA_HIVE, DOMAIN, HiveSession, refresh_system

SUPPORT_FLAGS_HEATER = SUPPORT_OPERATION_MODE

HIVE_TO_HASS_STATE = {"SCHEDULE": STATE_ECO, "ON": STATE_ON, "OFF": STATE_OFF}
HASS_TO_HIVE_STATE = {STATE_ECO: "SCHEDULE", STATE_ON: "ON", STATE_OFF: "OFF"}
SUPPORT_WATER_HEATER = [STATE_ECO, STATE_ON, STATE_OFF]
SERVICE_BOOST_HEATING = "boost_hotwater"
ATTR_TIME_PERIOD = "time_period"
ATTR_MODE = "on_off"
BOOST_HOTWATER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_TIME_PERIOD, default="00:30:00"): vol.All(
            cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds() // 60
        ),
        vol.Required(ATTR_MODE): cv.string,
    }
)


_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Hive water heater devices."""
    if discovery_info is None:
        return
    if discovery_info["HA_DeviceType"] != "HotWater":
        return

    session = hass.data.get(DATA_HIVE)
    water_heater = HiveWaterHeater(session, discovery_info)

    add_entities([water_heater])

    def hotwater_boost(service):
        """Handle the service call."""
        node_id = HiveSession.entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not node_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered.")
            return
        minutes = service.data.get(ATTR_TIME_PERIOD)
        mode = service.data[ATTR_MODE]

        if mode == "on":
            session.hotwater.turn_boost_on(node_id, minutes)
        elif mode == "off":
            session.hotwater.turn_boost_off(node_id)

    hass.services.register(
        DOMAIN, SERVICE_BOOST_HEATING, hotwater_boost, schema=BOOST_HOTWATER_SCHEMA
    )


class HiveWaterHeater(WaterHeaterDevice):
    """Hive Water Heater Device."""

    def __init__(self, hivesession, hivedevice):
        """Initialize the Water Heater device."""
        self.node_id = hivedevice["Hive_NodeID"]
        self.node_name = hivedevice["Hive_NodeName"]
        self.device_type = hivedevice["HA_DeviceType"]
        self.session = hivesession
        self._unique_id = f"{self.node_id}-{self.device_type}"
        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

    @property
    def name(self):
        """Return the name of the water heater."""
        if self.node_name is None:
            self.node_name = "Hot Water"
        return self.node_name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_operation(self):
        """Return current operation."""
        return HIVE_TO_HASS_STATE[self.session.hotwater.get_mode(self.node_id)]

    @property
    def operation_list(self):
        """List of available operation modes."""
        return SUPPORT_WATER_HEATER

    @refresh_system
    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        new_mode = HASS_TO_HIVE_STATE[operation_mode]
        self.session.hotwater.set_mode(self.node_id, new_mode)

    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.session.entity_lookup[self.entity_id] = self.node_id

    def update(self):
        """Update all Node data from Hive."""
        self.session.core.update_data(self.node_id)
