"""Read status of growatt inverters."""
import datetime
import logging
import growattServer
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PLANT_ID = "plant_id"
DEFAULT_UNIT = "kW"
DEFAULT_NAME = "Growatt"
SCAN_INTERVAL = datetime.timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PLANT_ID, default="0"): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Growatt sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    plant_id = config.get(CONF_PLANT_ID)
    name = config.get(CONF_NAME)

    api = growattServer.GrowattApi()

    # Log in to api and fetch first plant if no plant id is defined.
    user_id = api.login(username, password)["userId"]
    if plant_id == "0":
        plant_info = api.plant_list(user_id)
        plant_id = plant_info["data"][0]["plantId"]
        pass

    # Get a list of inverters for specified plant to add sensors for.
    inverters = api.inverter_list(plant_id)

    # Add a sensor for the total of the whole plant.
    add_devices(
        [GrowattInverter(api, name + "_Total", plant_id, username, password)], True
    )

    # Add sensors for each inverter in the specified plant.
    for inverter in inverters:
        add_devices(
            [
                GrowattInverter(
                    api,
                    name + "_" + inverter["deviceAilas"],
                    inverter["deviceSn"],
                    username,
                    password,
                )
            ],
            True,
        )


class GrowattInverter(Entity):
    """Representation of a Growattt Sensor."""

    def __init__(self, api, name, inverter_id, u, p):
        """Initialize a PVOutput sensor."""
        self.api = api
        self._name = name
        self.inverter_id = inverter_id
        self.username = u
        self.password = p
        self.is_total = "Total" in name and inverter_id.isdigit()
        self._state = None
        self.attributes = {}
        self._unit_of_measurement = "W"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        attributes = self.attributes
        attributes["icon"] = "mdi:solar-power"
        return attributes

    def update(self):
        """Get the latest data from the Growat API and updates the state."""
        try:
            self.api.login(self.username, self.password)
            if self.is_total:
                total_info = self.api.plant_info(self.inverter_id)
                del total_info["deviceList"]
                self._state = total_info["invTodayPpv"]
                self.attributes = total_info
            else:
                inverter_info = self.api.inverter_detail(self.inverter_id)

                self.attributes = inverter_info["data"]
                self._state = inverter_info["data"]["pac"]
        except TypeError:
            _LOGGER.error("Unable to fetch data from Growatt server. %s")
