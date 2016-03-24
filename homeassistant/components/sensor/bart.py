"""
Support for the BART (Bay Area Rapid Transit) API.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bart/
"""
import logging
from datetime import timedelta

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen
from lxml import etree

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['beautifulsoup4==4.4.1', 'lxml==3.6.0']

ICON = 'mdi:train'

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

def parse_api_response(raw_xml):
    """Parse the BART API response."""
    if isinstance(raw_xml, bytes):
        parsed_xml = etree.fromstring(
            raw_xml, parser=etree.XMLParser(
                encoding='utf-8'))
    else:
        parsed_xml = etree.parse(raw_xml)
    return parsed_xml

def get_bart_xml(url):
    """Helper function to query the BART API."""
    raw_response = urlopen(url)
    xml = parse_api_response(raw_response)
    return xml

def parse_bart_etd(etd, origin):
    """Parse time estimate into usable format."""
    raw_estimates = etd.findall("estimate")
    estimates = []
    for estimate in raw_estimates:
        appending_estimate = dict(
            (("departure_" + elt.tag, elt.text) for elt in estimate))
        if appending_estimate["departure_minutes"] == "Leaving":
            appending_estimate["departure_minutes"] = "0"
        appending_estimate["departure_destination"] = etd.find(
            "destination").text
        appending_estimate["departure_abbreviation"] = etd.find(
            "abbreviation").text
        appending_estimate["provided_station"] = origin
        estimates.append(appending_estimate)
    return estimates

# pylint: disable=too-few-public-methods
class BARTAPIClient(object):
    """The Class for accessing the BART API."""

    def __init__(self, api_key="MW9S-E7SL-26DU-VV8V"):
        """Init the BART API client."""
        self.api_key = api_key

    def bsa(self, stn="ALL"):
        """Get service advisories from the BART API."""
        xml = get_bart_xml(
            "http://api.bart.gov/api/bsa.aspx?cmd=bsa&orig=%s&key=%s" %
            (stn, self.api_key))
        raw_advisories = xml.findall(".//bsa")
        advisory_list = []
        for advisory in raw_advisories:
            appending_advisory = dict(
                (("advisory_" + elt.tag, elt.text) for elt in advisory))
            appending_advisory["provided_station"] = stn
            advisory_list.append(appending_advisory)
        return advisory_list

    def etd(self, station="ALL", lines=None):
        """Get estimated time to departures from the BART API."""
        xml = get_bart_xml(
            "http://api.bart.gov/api/etd.aspx?cmd=etd&orig=%s&key=%s" %
            (station, self.api_key))
        raw_etds = xml.findall(".//etd")
        etd_list = []
        for etd in raw_etds:
            if lines is not None and etd.find("abbreviation").text in lines:
                etd_list.extend(parse_bart_etd(etd, station))
            elif lines is None:
                etd_list.extend(parse_bart_etd(etd, station))
        return sorted(etd_list, key=lambda k: int(k['departure_minutes']))


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the BART public transport sensor."""

    if None in (config.get('origin'), config.get('lines')):
        _LOGGER.error("Origin or lines not set in Home Assistant config")
        return False

    dev = []
    departures = DeparturesData(config.get('origin'), config.get('lines'))
    advisories = AdvisoriesData(config.get('origin'))
    etd_iterator = 1
    advisory_iterator = 1
    for etd in departures.departures:
        dev.append(BARTDepartureSensor(departures, etd, etd_iterator))
        etd_iterator += 1
    for advisory in advisories.advisories:
        dev.append(BARTAdvisorySensor(advisories, advisory, advisory_iterator))
        advisory_iterator += 1
    add_devices(dev)

NUMBER_NAMES = {
    1: 'First',
    2: 'Second',
    3: 'Third',
    4: 'Fourth',
    5: 'Fifth',
    6: 'Sixth',
    7: 'Seventh',
    8: 'Eighth',
    9: 'Ninth',
    10: 'Tenth',
}

# pylint: disable=too-few-public-methods
class BARTDepartureSensor(Entity):
    """Implementation of an BART API departures sensor."""

    def __init__(self, data, estimate, iteration):
        """Initialize the sensor."""
        self.data = data
        self._name = 'BART Departure ' + str(iteration)
        self.friendly_name = NUMBER_NAMES[iteration] + ' BART Departure'
        self._unit_of_measurement = "min"
        self._state = 0
        self._iteration = iteration
        self._departure = self.data.departures[self._iteration - 1]
        self.update()

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
        """Return the state attributes."""
        return self._departure

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data from the BART API and update the states."""
        self.data.update()
        try:
            self._departure = self.data.departures[self._iteration - 1]
            self._state = self._departure["departure_minutes"]
        except TypeError:
            pass

# pylint: disable=too-few-public-methods
class BARTAdvisorySensor(Entity):
    """Implementation of an BART API advisories sensor."""

    def __init__(self, data, estimate, iteration):
        """Initialize the sensor."""
        self.data = data
        self._name = 'BART Advisory ' + str(iteration)
        self.friendly_name = NUMBER_NAMES[iteration] + ' BART Advisory'
        self._state = "Inactive"
        self._iteration = iteration
        self._advisory = self.data.advisories[self._iteration - 1]
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return "Active"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._advisory

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data from the BART API and update the states."""
        self.data.update()
        try:
            self._advisory = self.data.advisories[self._iteration - 1]
        except TypeError:
            pass

# pylint: disable=too-few-public-methods
class DeparturesData(object):
    """The Class for handling the departures data retrieval."""

    def __init__(self, origin, lines):
        """Initialize the data object."""
        self.origin = origin
        self.lines = lines
        self.departures = None
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest departures from the BART API."""
        bart = BARTAPIClient()
        self.departures = bart.etd(self.origin, self.lines)

# pylint: disable=too-few-public-methods
class AdvisoriesData(object):
    """The Class for handling the advisories data retrieval."""

    def __init__(self, origin):
        """Initialize the data object."""
        self.origin = origin
        self.advisories = None
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest advisories from the BART API."""
        bart = BARTAPIClient()
        self.advisories = bart.bsa(self.origin)
