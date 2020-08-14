"""Definition and setup of the Omnilogic Sensors for Home Assistant."""

from datetime import timedelta
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

TEMP_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]
PERCENT_UNITS = [UNIT_PERCENTAGE, UNIT_PERCENTAGE]
SALT_UNITS = ["g/L", "ppm"]

SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = []

    for backyard in coordinator.data:
        """Add backyard level sensors."""

        """Air Temperature."""
        sensors.append(
            OmnilogicSensor(
                coordinator,
                "air_temperature",
                "Air Temperature",
                backyard,
                {},
                "temperature",
                "mdi:thermometer",
                TEMP_UNITS,
                backyard.get("airTemp"),
            )
        )
        _LOGGER.info("OmniLogic - air temperature for backyard set up successfully.")

        for bow in backyard["BOWS"]:
            """Add bow level sensors."""

            """Water Temperature."""
            try:
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "water_temperature",
                        "Water Temperature",
                        backyard,
                        bow,
                        "temperature",
                        "mdi:thermometer",
                        TEMP_UNITS,
                        bow.get("waterTemp"),
                    )
                )
                _LOGGER.info(
                    "OmniLogic - water temperature for "
                    + bow["Name"]
                    + " set up successfully."
                )
            except Exception as ex:
                _LOGGER.info(
                    "OmniLogic - no water temperature to set up. (" + str(ex) + ")"
                )

            """Filter Pump."""
            try:
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "filter_pump_speed",
                        "Pump Speed",
                        backyard,
                        bow,
                        "none",
                        "mdi:speedometer",
                        PERCENT_UNITS,
                        bow["Filter"],
                    )
                )
                _LOGGER.info(
                    "OmnilLogic - filter pump "
                    + bow["Filter"]["Name"]
                    + " set up successfully."
                )
            except Exception as ex:
                _LOGGER.info("OmniLogic - No filter pump to set up. (" + str(ex) + ")")

            """All other pumps."""
            try:
                for pump in bow["Pumps"]:
                    sensors.append(
                        OmnilogicSensor(
                            coordinator,
                            "pump_speed",
                            "Pump Speed",
                            backyard,
                            bow,
                            "none",
                            "mdi:speedometer",
                            PERCENT_UNITS,
                            pump,
                        )
                    )
                    _LOGGER.info(
                        "OmniLogic - pump " + pump["Name"] + " set up successfully."
                    )
            except Exception as ex:
                _LOGGER.info(
                    "Omnilogic - No additional pumps to set up. (" + str(ex) + ")"
                )

            """Chlorinator Information."""
            try:
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "chlorinator",
                        "Chlorinator",
                        backyard,
                        bow,
                        "none",
                        "mdi:gauge",
                        PERCENT_UNITS,
                        bow["Chlorinator"],
                    )
                )
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "salt_level",
                        "Salt Level",
                        backyard,
                        bow,
                        "none",
                        "mdi:gauge",
                        PERCENT_UNITS,
                        bow["Chlorinator"],
                    )
                )
                _LOGGER.info(
                    "OmniLogic - chlorinator "
                    + bow["Chlorinator"]["Name"]
                    + " set up successfully."
                )
            except Exception as ex:
                _LOGGER.info("OmniLogic - no chlorinator to set up. (" + str(ex) + ")")

            """CSAD Water Balance Sensors."""
            try:
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "csad_ph",
                        "CSAD",
                        backyard,
                        bow,
                        "none",
                        "mdi:gauge",
                        PERCENT_UNITS,
                        bow["CSAD"],
                    )
                )
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "csad_orp",
                        "CSAD",
                        backyard,
                        bow,
                        "none",
                        "mdi:gauge",
                        PERCENT_UNITS,
                        bow["CSAD"],
                    )
                )
                _LOGGER.info("OmniLogic - successfully parsed CSAD data.")
            except Exception as ex:
                _LOGGER.info("OmniLogic - no CSAD data available. (" + str(ex) + ")")

    async_add_entities(sensors, update_before_add=True)


class OmnilogicSensor(Entity):
    """Defines an Omnilogic sensor entity."""

    def __init__(
        self,
        coordinator,
        kind,
        name,
        backyard,
        bow,
        device_class,
        icon,
        unit,
        sensordata,
    ):
        """Initialize Entities."""
        if bow != {}:
            """This is a bow sensor."""
            sensorname = (
                "omni_"
                + backyard["BackyardName"].replace(" ", "_")
                + "_"
                + bow["Name"].replace(" ", "_")
                + "_"
                + kind
            )
        else:
            """This is a back yard level sensor."""
            sensorname = (
                "omni_" + backyard["BackyardName"].replace(" ", "_") + "_" + kind
            )

        self._kind = kind
        self._name = None
        self.entity_id = ENTITY_ID_FORMAT.format(sensorname)
        self._backyard = backyard
        self._backyard_name = backyard["BackyardName"]
        self._state = None
        self._unit_type = backyard["Unit-of-Measurement"]
        self._device_class = device_class
        self._icon = icon
        self._bow = bow
        self._unit = None
        self.coordinator = coordinator
        self.bow = bow
        self.sensordata = sensordata
        self.attrs = {}
        self.attrs["MspSystemId"] = backyard["systemId"]

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return True

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self.entity_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the entity."""
        if self._device_class != "none":
            return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the right unit of measure."""
        return self._unit

    @property
    def icon(self):
        """Return the icon for the entity."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        return self.attrs

    @property
    def force_update(self):
        """Force update."""
        return True

    @property
    def state(self):
        """Return the state."""
        return self._state

    async def async_update(self):
        """Update Omnilogic entity."""
        await self.coordinator.async_request_refresh()

        if self._kind == "water_temperature":
            """Find the right bow for updated data."""
            sensordata = None

            for backyard in self.coordinator.data:
                for bow in backyard["BOWS"]:
                    if bow["systemId"] == self.bow["systemId"]:
                        sensordata = bow["waterTemp"]
                        break

            temp_return = float(sensordata)
            unit_of_measurement = TEMP_FAHRENHEIT
            if self._backyard["Unit-of-Measurement"] == "Metric":
                temp_return = round((temp_return - 32) * 5 / 9, 1)
                unit_of_measurement = TEMP_CELSIUS

            self.attrs["hayward_temperature"] = temp_return
            self.attrs["hayward_unit_of_measure"] = unit_of_measurement
            self._state = float(sensordata)
            self._unit = TEMP_FAHRENHEIT
            self.attrs["systemId"] = self.bow.get("systemId")
            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " Water Temperature"
            )

        elif self._kind == "filter_pump_speed":
            """Find the right filter_pump for updated data."""
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["Filter"]["systemId"] == self.sensordata.get("systemId"):
                        sensordata = bow["Filter"]
                        break

            self._state = sensordata.get("filterSpeed")
            self._unit = "%"
            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " "
                + self.sensordata.get("Name")
            )
            self.attrs["systemId"] = self.sensordata.get("systemId")
            self.attrs["MspSystemId"] = self._backyard["systemId"]
            self.attrs["PumpType"] = self.sensordata.get("Filter-Type")

        elif self._kind == "pump_speed":
            """Find the right pump for the updated data."""
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    for pump in bow.get("Pumps"):
                        if pump["systemId"] == self.sensordata["systemId"]:
                            sensordata = pump
                            break

            if self.sensordata.get("Type") == "PMP_SINGLE_SPEED":
                if sensordata.get("pumpSpeed") == "100":
                    self._state = "on"
                else:
                    self._state = "off"
            else:
                self._state = sensordata.get("pumpSpeed")
                self._unit = "%"

            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " "
                + self.sensordata.get("Name")
            )
            self.attrs["systemId"] = self.sensordata.get("systemId")
            self.attrs["MspSystemId"] = self._backyard["systemId"]
            self.attrs["PumpType"] = self.sensordata.get("Type")

        elif self._kind == "salt_level":
            """Find the right chlorinator for the updated data."""
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["Chlorinator"]["systemId"] == self.sensordata["systemId"]:
                        sensordata = bow.get("Chlorinator")
                        break

            salt_return = float(sensordata.get("avgSaltLevel"))
            unit_of_measurement = "ppm"

            if self._backyard["Unit-of-Measurement"] == "Metric":
                salt_return = round(salt_return / 1000, 2)
                unit_of_measurement = "g/L"

            self._state = salt_return
            self._unit = unit_of_measurement
            self.attrs["SystemId"] = self.sensordata.get("systemId")
            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " "
                + self.sensordata.get("Name")
                + " Salt Level"
            )

        elif self._kind == "chlorinator":
            """Find the right chlorinator for the updated data."""
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["Chlorinator"]["systemId"] == self.sensordata["systemId"]:
                        sensordata = bow.get("Chlorinator")
                        break

            self._state = sensordata.get("Timed-Percent")
            self._unit = "%"
            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " "
                + self.sensordata.get("Name")
                + " Setting"
            )

        elif self._kind == "csad_ph":
            """Find the right CSAD for the updated data."""
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["CSAD"]["systemId"] == self.sensordata["systemId"]:
                        sensordata = bow.get("CSAD")
                        break

            self._state = sensordata.get("ph")
            self._unit = "pH"
            self._name = (
                self._backyard["BackyardName"] + " " + self.bow.get("Name") + " pH"
            )

        elif self._kind == "csad_orp":
            """Find the right CSAD for the updated data."""
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["CSAD"]["systemId"] == self.sensordata["systemId"]:
                        sensordata = bow.get("CSAD")
                        break

            self._state = sensordata.get("orp")
            self._unit = "mV"
            self._name = (
                self._backyard["BackyardName"] + " " + self.bow.get("Name") + " ORP"
            )

        elif self._kind == "air_temperature":
            """Find the right system for the updated data."""
            sensordata = 0

            for backyard in self.coordinator.data:
                if backyard.get("systemId") == self.attrs["MspSystemId"]:
                    sensordata = backyard.get("airTemp")

            temp_return = float(sensordata)
            unit_of_measurement = TEMP_FAHRENHEIT
            if self._backyard["Unit-of-Measurement"] == "Metric":
                temp_return = round((temp_return - 32) * 5 / 9, 1)
                unit_of_measurement = TEMP_CELSIUS

            self.attrs["hayward_temperature"] = temp_return
            self.attrs["hayward_unit_of_measure"] = unit_of_measurement
            self._state = float(sensordata)
            self._unit = TEMP_FAHRENHEIT
            self._name = self._backyard.get("BackyardName") + " Air Temperature"
            self.attrs["MspSystemId"] = self._backyard["systemId"]

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
