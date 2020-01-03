"""Support for OpenERZ API for Zurich city waste disposal system."""
from datetime import datetime, timedelta
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=12)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("zip"): cv.string,
        vol.Required("waste_type", default="waste"): cv.string,
        vol.Optional("name"): cv.string,
    }
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    openerz_config = {
        "zip": config["zip"],
        "waste_type": config["waste_type"],
        "name": config.get("name"),
    }
    add_entities([OpenERZSensor(openerz_config)])


class OpenERZSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, openerz_config):
        """Initialize the sensor."""
        self._state = None
        self.openerz_config = openerz_config
        self.zip = self.openerz_config["zip"]
        self.waste_type = self.openerz_config["waste_type"]
        self.friendly_name = self.openerz_config.get("name")
        self.start_date = datetime.now()
        self.end_date = None
        self.last_api_response = None

        self.update()

    def update_start_date(self):
        """Set the start day to today."""

        self.start_date = datetime.now()

    def find_end_date(self, day_offset=31):
        """Find the end date for the request, given an offset expressed in days.

        Args:
        day_offset (int): difference in days between start and end date of the request
        """

        self.end_date = self.start_date + timedelta(days=day_offset)

    def make_api_request(self):
        """Construct a request and send it to the OpenERZ API."""

        headers = {"accept": "application/json"}

        start_date = self.start_date.strftime("%Y-%m-%d")
        end_date = self.end_date.strftime("%Y-%m-%d")

        payload = {
            "zip": self.zip,
            "start": start_date,
            "end": end_date,
            "offset": 0,
            "limit": 0,
            "lang": "en",
            "sort": "date",
        }
        url = f"http://openerz.metaodi.ch/api/calendar/{self.waste_type}.json"

        try:
            self.last_api_response = requests.get(url, params=payload, headers=headers)
        except requests.exceptions.ConnectionError as e:
            _LOGGER.error("ConnectionError while making request to OpenERZ: %s", e)

    def parse_api_response(self):
        """Parse the JSON response received from the OpenERZ API and return a date of the next pickup."""

        if not self.last_api_response.ok:
            _LOGGER.warning(
                "Last request to OpenERZ was not succesful. Status code: %d",
                self.last_api_response.status_code,
            )
            return None

        response_json = self.last_api_response.json()
        if response_json["_metadata"]["total_count"] == 0:
            _LOGGER.warning("Request to OpenERZ returned no results.")
            return None
        result_list = response_json.get("result")
        first_scheduled_pickup = result_list[0]
        if (
            first_scheduled_pickup["zip"] == self.zip
            and first_scheduled_pickup["type"] == self.waste_type
        ):
            return first_scheduled_pickup["date"]
        else:
            _LOGGER.warning(
                "Either zip or waste type does not match the ones specified in the configuration."
            )
            return None

    @property
    def name(self):
        """Return the name of the sensor."""

        return (
            f"ERZ - {self.friendly_name} ({self.zip})"
            if self.friendly_name
            else "Zürich Entsorgungs-Kalender"
        )

    @property
    def state(self):
        """Return the state of the sensor."""

        return self._state

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        self.update_start_date()
        self.find_end_date(day_offset=31)
        self.make_api_request()
        self._state = self.parse_api_response()
