"""Support for the Hive climate devices."""
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_BOOST,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    PRESET_NONE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import DATA_HIVE, DOMAIN

HIVE_TO_HASS_STATE = {
    "SCHEDULE": HVAC_MODE_AUTO,
    "MANUAL": HVAC_MODE_HEAT,
    "OFF": HVAC_MODE_OFF,
}

HASS_TO_HIVE_STATE = {
    HVAC_MODE_AUTO: "SCHEDULE",
    HVAC_MODE_HEAT: "MANUAL",
    HVAC_MODE_OFF: "OFF",
}

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_HVAC = [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]
SUPPORT_PRESET = [PRESET_NONE, PRESET_BOOST]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Hive climate devices."""
    if discovery_info is None:
        return
    if discovery_info["HA_DeviceType"] != "Heating":
        return

    session = hass.data.get(DATA_HIVE)
    climate = HiveClimateEntity(session, discovery_info)

    add_entities([climate])


class HiveClimateEntity(ClimateDevice):
    """Hive Climate Device."""

    def __init__(self, hivesession, hivedevice):
        """Initialize the Climate device."""
        self.node_id = hivedevice["Hive_NodeID"]
        self.node_name = hivedevice["Hive_NodeName"]
        self.device_type = hivedevice["HA_DeviceType"]
        self.thermostat_node_id = hivedevice["Thermostat_NodeID"]
        self.session = hivesession
        self.attributes = {}
        self.data_updatesource = "{}.{}".format(self.device_type, self.node_id)
        self._unique_id = "{}-{}".format(self.node_id, self.device_type)

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
        return SUPPORT_FLAGS

    def handle_update(self, updatesource):
        """Handle the new update request."""
        if "{}.{}".format(self.device_type, self.node_id) not in updatesource:
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the Climate device."""
        friendly_name = "Heating"
        if self.node_name is not None:
            friendly_name = "{} {}".format(self.node_name, friendly_name)
        return friendly_name

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return HIVE_TO_HASS_STATE[self.session.heating.get_mode(self.node_id)]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.session.heating.current_temperature(self.node_id)

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self.session.heating.get_target_temperature(self.node_id)

    @property
    def min_temp(self):
        """Return minimum temperature."""
        return self.session.heating.min_temperature(self.node_id)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.session.heating.max_temperature(self.node_id)

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self.session.heating.get_boost(self.node_id) == "ON":
            return PRESET_BOOST
        return None

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.session.entities.append(self)

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        new_mode = HASS_TO_HIVE_STATE[hvac_mode]
        self.session.heating.set_mode(self.node_id, new_mode)

        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            self.session.heating.set_target_temperature(self.node_id, new_temperature)

            for entity in self.session.entities:
                entity.handle_update(self.data_updatesource)

    def set_preset_mode(self, preset_mode) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_NONE and self.preset_mode == PRESET_BOOST:
            self.session.heating.turn_boost_off(self.node_id)

        elif preset_mode == PRESET_BOOST:
            curtemp = self.session.heating.current_temperature(self.node_id)
            curtemp = round(curtemp * 2) / 2
            temperature = curtemp + 0.5

            self.session.heating.turn_boost_on(self.node_id, 30, temperature)

        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def update(self):
        """Update all Node data from Hive."""
        self.session.core.update_data(self.node_id)
        self.attributes = self.session.attributes.state_attributes(
            self.thermostat_node_id
        )
