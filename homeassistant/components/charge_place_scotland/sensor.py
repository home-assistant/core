"""CPS Sensor."""
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import datetime
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

api_fragment = "/chargepoints/search?location={}"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required("station_id"): cv.string, vol.Optional("name"): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up CPS sensor."""
    conf = hass.data["charge_place_scotland"]
    name = config.get("name")
    station = config.get("station_id")
    sensor_list = []
    result = requests.get(
        conf.get("base_url").format(api_fragment).format(station)
    ).json()
    for i in result["chargePoints"][0]["connectorStatus"]:
        connector = result["chargePoints"][0]["connectorStatus"][i]
        sensor_list.append(
            ChargingStationEntity(
                name,
                station,
                conf.get("base_url").format(api_fragment),
                connector["socketType"],
                i,
            )
        )
    add_entities(sensor_list, True)


class ChargingStationEntity(Entity):
    """CPS Sensor Class."""

    def __init__(self, name, station_id, api_url, connector, position):
        """CPS class constructor."""
        self.station_id = station_id
        self.api_url = api_url
        self._position = position
        result = requests.get(self.api_url.format(self.station_id)).json()
        if name:
            self._name = name
        else:
            self._name = result["chargePoints"][0]["siteName"]
        self.entity_id = "sensor.cps_{}_{}_{}".format(
            station_id, slugify(connector), position
        )
        self.connector_type = connector
        self.attribute_map(result)

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Perform Update."""
        result = requests.get(self.api_url.format(self.station_id)).json()
        self._state = result["chargePoints"][0]["lastKnownStatus"]
        self.attribute_map(result)

    def attribute_map(self, result):
        """Map attributes."""

        self.last_successful_update = datetime.datetime.now()
        self._state = result["chargePoints"][0]["connectorStatus"][self._position][
            "status"
        ]
        self.lastStatusUpdateTs = result["chargePoints"][0]["connectorStatus"][
            self._position
        ]["lastConnectorStatusUpdateTs"]
        self.lat = result["chargePoints"][0]["lat"]
        self.long = result["chargePoints"][0]["lon"]
        self.locationOnSite = result["chargePoints"][0]["locationOnSite"]

    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {
            "last_successful_update": self.last_successful_update,
            "lastStatusUpdateTs": self.lastStatusUpdateTs,
            "lat": self.lat,
            "long": self.long,
            "locationOnSite": self.locationOnSite,
            "connector_type": self.connector_type,
        }
        return state_attr
