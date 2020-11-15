"""Sensor for checking the status of London air."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import HTTP_OK
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_LOCATIONS = "locations"

SCAN_INTERVAL = timedelta(minutes=30)

AUTHORITIES = [
    "Barking and Dagenham",
    "Bexley",
    "Brent",
    "Camden",
    "City of London",
    "Croydon",
    "Ealing",
    "Enfield",
    "Greenwich",
    "Hackney",
    "Haringey",
    "Harrow",
    "Havering",
    "Hillingdon",
    "Islington",
    "Kensington and Chelsea",
    "Kingston",
    "Lambeth",
    "Lewisham",
    "Merton",
    "Redbridge",
    "Richmond",
    "Southwark",
    "Sutton",
    "Tower Hamlets",
    "Wandsworth",
    "Westminster",
]

URL = (
    "http://api.erg.kcl.ac.uk/AirQuality/Hourly/"
    "MonitoringIndex/GroupName=London/Json"
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LOCATIONS, default=AUTHORITIES): vol.All(
            cv.ensure_list, [vol.In(AUTHORITIES)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the London Air sensor."""
    data = APIData()
    data.update()
    sensors = []
    for name in config.get(CONF_LOCATIONS):
        sensors.append(AirSensor(name, data))

    add_entities(sensors, True)


class APIData:
    """Get the latest data for all authorities."""

    def __init__(self):
        """Initialize the AirData object."""
        self.data = None

    # Update only once in scan interval.
    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from TFL."""
        response = requests.get(URL, timeout=10)
        if response.status_code != HTTP_OK:
            _LOGGER.warning("Invalid response from API")
        else:
            self.data = parse_api_response(response.json())


class AirSensor(Entity):
    """Single authority air sensor."""

    ICON = "mdi:cloud-outline"

    def __init__(self, name, APIdata):
        """Initialize the sensor."""
        self._name = name
        self._api_data = APIdata
        self._site_data = None
        self._state = None
        self._updated = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def site_data(self):
        """Return the dict of sites data."""
        return self._site_data

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attrs = {}
        attrs["updated"] = self._updated
        attrs["sites"] = len(self._site_data) if self._site_data is not None else 0
        attrs["data"] = self._site_data
        return attrs

    def update(self):
        """Update the sensor."""
        sites_status = []
        self._api_data.update()
        if self._api_data.data:
            self._site_data = self._api_data.data[self._name]
            self._updated = self._site_data[0]["updated"]
            for site in self._site_data:
                if site["pollutants_status"] != "no_species_data":
                    sites_status.append(site["pollutants_status"])

        if sites_status:
            self._state = max(set(sites_status), key=sites_status.count)
        else:
            self._state = None


def parse_species(species_data):
    """Iterate over list of species at each site."""
    parsed_species_data = []
    quality_list = []
    for species in species_data:
        if species["@AirQualityBand"] != "No data":
            species_dict = {}
            species_dict["description"] = species["@SpeciesDescription"]
            species_dict["code"] = species["@SpeciesCode"]
            species_dict["quality"] = species["@AirQualityBand"]
            species_dict["index"] = species["@AirQualityIndex"]
            species_dict[
                "summary"
            ] = f"{species_dict['code']} is {species_dict['quality']}"
            parsed_species_data.append(species_dict)
            quality_list.append(species_dict["quality"])
    return parsed_species_data, quality_list


def parse_site(entry_sites_data):
    """Iterate over all sites at an authority."""
    authority_data = []
    for site in entry_sites_data:
        site_data = {}
        species_data = []

        site_data["updated"] = site["@BulletinDate"]
        site_data["latitude"] = site["@Latitude"]
        site_data["longitude"] = site["@Longitude"]
        site_data["site_code"] = site["@SiteCode"]
        site_data["site_name"] = site["@SiteName"].split("-")[-1].lstrip()
        site_data["site_type"] = site["@SiteType"]

        if isinstance(site["Species"], dict):
            species_data = [site["Species"]]
        else:
            species_data = site["Species"]

        parsed_species_data, quality_list = parse_species(species_data)

        if not parsed_species_data:
            parsed_species_data.append("no_species_data")
        site_data["pollutants"] = parsed_species_data

        if quality_list:
            site_data["pollutants_status"] = max(
                set(quality_list), key=quality_list.count
            )
            site_data["number_of_pollutants"] = len(quality_list)
        else:
            site_data["pollutants_status"] = "no_species_data"
            site_data["number_of_pollutants"] = 0

        authority_data.append(site_data)
    return authority_data


def parse_api_response(response):
    """Parse return dict or list of data from API."""
    data = dict.fromkeys(AUTHORITIES)
    for authority in AUTHORITIES:
        for entry in response["HourlyAirQualityIndex"]["LocalAuthority"]:
            if entry["@LocalAuthorityName"] == authority:

                if isinstance(entry["Site"], dict):
                    entry_sites_data = [entry["Site"]]
                else:
                    entry_sites_data = entry["Site"]

                data[authority] = parse_site(entry_sites_data)

    return data
