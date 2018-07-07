"""
Support for the Environment Canada radar imagery.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.environment_canada/
"""
import os
import json
import logging
import datetime
import xml.etree.ElementTree as et

import requests
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA, Camera)
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, ATTR_ATTRIBUTION)
from homeassistant.util import Throttle
from homeassistant.util.location import distance
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['imageio==2.3.0',
                'requests-futures==0.9.7']

_LOGGER = logging.getLogger(__name__)

ATTR_STATION = 'station'
ATTR_LOCATION = 'location'

CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = 'station'
CONF_LOOP = 'loop'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)
MAX_CACHE_AGE = datetime.timedelta(days=30)
FRAME_URL = 'http://dd.weatheroffice.ec.gc.ca/radar/' \
               'PRECIPET/GIF/{0}/{1}_{0}_{2}PRECIPET_RAIN.gif'
LOOP_FRAMES = 12
LOOP_FPS = 6

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOOP, default=True): cv.boolean,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'latlon'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'latlon'): cv.longitude,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Environment Canada camera."""
    station = get_station(hass, config)
    radar_object = ECRadar(hass, station['code'], config.get(CONF_LOOP, True))

    try:
        radar_object.update()
    except ValueError as err:
        _LOGGER.error("Received error from EC radar: %s", err)
        return

    add_devices([ECCamera(radar_object, station, config.get(CONF_NAME))])


class ECCamera(Camera):
    """Implementation of an Environment Canada radar camera."""

    def __init__(self, radar_object, station, camera_name):
        """Initialize the camera."""
        super().__init__()

        self.radar_object = radar_object
        self.station = station
        self.camera_name = camera_name
        self.content_type = 'image/gif'

    def camera_image(self):
        """Return bytes of camera image."""
        self.radar_object.update()
        return self.radar_object.data

    @property
    def name(self):
        """Return the name of the camera."""
        if self.camera_name is not None:
            return self.camera_name
        return ' '.join([self.station['name'], 'Radar'])

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_LOCATION: self.station['name'],
            ATTR_STATION: self.station['code']
        }

        return attr

    def update(self):
        """Update radar image."""
        self.radar_object.update()


class ECRadar(object):
    """Get radar image from Environment Canada."""

    def __init__(self, hass, station_code, loop):
        """Initialize the data object."""
        self.hass = hass
        self.station_code = station_code
        self.loop = loop
        self.image_bytes = None
        self.composite = self.detect_composite()

    @property
    def data(self):
        """Return the latest data object."""
        if self.image_bytes:
            return self.image_bytes
        return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest image or loop from Environment Canada."""
        if self.loop is True:
            self.image_bytes = self.get_loop()
        else:
            self.image_bytes = self.get_latest_frame()

    def detect_composite(self):
        """Detect if a station is returning regular or composite images."""
        url = FRAME_URL.format(self.station_code, self.frame_time(10), '')
        if requests.get(url=url).status_code != 404:
            return ''
        else:
            url = FRAME_URL.format(self.station_code, self.frame_time(10),
                                   'COMP_')
            if requests.get(url=url).status_code != 404:
                return 'COMP_'
        _LOGGER.error("Could not get radar images for station %s",
                      self.station_code)
        return None

    @staticmethod
    def frame_time(mins_ago):
        """Return the timestamp of a frame from at least x minutes ago."""
        time_string = (datetime.datetime.utcnow() -
                       datetime.timedelta(minutes=mins_ago)) \
            .strftime('%Y%m%d%H%M')
        time_string = time_string[:-1] + '0'
        return time_string

    def get_frames(self, count):
        """Get a list of images from Environment Canada."""
        from requests_futures.sessions import FuturesSession

        frames = []
        futures = []
        session = FuturesSession(max_workers=5)

        for mins_ago in range(10 * count, 0, -10):
            time_string = self.frame_time(mins_ago)
            url = FRAME_URL.format(self.station_code,
                                   time_string,
                                   self.composite)
            futures.append(session.get(url=url))

        for future in futures:
            frames.append(future.result().content)
        for i in range(0, 2):             # pylint: disable=unused-variable
            frames.append(frames[count - 1])

        return frames

    def get_loop(self):
        """Build an animated GIF of recent radar images."""
        import imageio

        frames = self.get_frames(LOOP_FRAMES)
        gifs = []

        for frame in frames:
            gifs.append(imageio.imread(frame))

        return imageio.mimwrite(imageio.RETURN_BYTES,
                                gifs, format='GIF', fps=LOOP_FPS)

    def get_latest_frame(self):
        """Get the latest image from Environment Canada."""
        return self.get_frames(1)[0]


def get_radar_sites():
    """Get list of radar sites from Wikipedia."""
    xml_string = requests.get('https://tools.wmflabs.org/kmlexport'
                              '?article=Canadian_weather_radar_network').text
    root = et.fromstring(xml_string)
    namespace = {'ns': 'http://earth.google.com/kml/2.1'}
    folder = root.find('ns:Document/ns:Folder', namespace)

    site_list = []

    for site in folder.findall('ns:Placemark', namespace):
        code = site.find('ns:name', namespace).text[1:4]
        name = site.find('ns:name', namespace).text[7:]
        lat = site.find('ns:Point/ns:coordinates',
                        namespace).text.split(',')[1]
        lon = site.find('ns:Point/ns:coordinates',
                        namespace).text.split(',')[0]

        site_list.append({'code': code,
                          'name': name,
                          'lat': lat,
                          'lon': lon})
    return site_list


def cache_expired(file):
    """Return whether cache should be refreshed."""
    cache_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file))
    return datetime.datetime.utcnow() - cache_mtime > MAX_CACHE_AGE


def radar_sites(cache_dir):
    """Return list of all sites, for auto-config.

    Results from internet requests are cached, making
    subsequent calls faster.
    """
    cache_file = os.path.join(cache_dir, '.ec-radars.json')

    if not os.path.isfile(cache_file) or cache_expired(cache_file):
        sites = get_radar_sites()

        with open(cache_file, 'w') as cache:
            cache.write(json.dumps(sites))
        return sites
    else:
        with open(cache_file, 'r') as cache:
            return json.loads(cache.read())


def closest_site(lat, lon, cache_dir):
    """Return the site code of the closest radar to our lat/lon."""
    if lat is None or lon is None or not os.path.isdir(cache_dir):
        return

    sites = radar_sites(cache_dir)

    def site_distance(site):
        """Calculate distance to a site."""
        return distance(lat, lon, float(site['lat']), float(site['lon']))

    closest = min(sites, key=site_distance)

    return closest


def get_station(hass, config):
    """Determine station to use.

    Preference is for user-provided station ID, followed by closest station to
    platform-specific coordinates, then closest station to
    top-level coordinates.
    """
    cache_dir = hass.config.config_dir
    station = None

    if config.get(CONF_STATION):
        for site in radar_sites(cache_dir):
            if site.get(CONF_STATION):
                station = site
    elif config.get(CONF_LATITUDE) and config.get(CONF_LONGITUDE):
        station = closest_site(
            config[CONF_LATITUDE],
            config[CONF_LONGITUDE],
            cache_dir)
    else:
        station = closest_site(
            hass.config.latitude,
            hass.config.longitude,
            cache_dir)

    if station is None:
        _LOGGER.error("Could not get radar station")
        return None

    return station
