"""

This component provides animated GIF images of weather-radar imagery derived
the Australian Bureau of Meteorology (http://www.bom.gov.au/australia/radar/),
suitable for display in e.g. a Picture Entity card. The full configuration
options are:

camera:
  - platform: bomradarloop
    location: <location-name>
    name: <entity-name>
    filename: /config/www/loop.gif
    id: <radar-id>
    frames: <frames-per-animation>
    delta: <seconds-between-frames>

A simple full example configuration:

camera:
  - platform: bomradarloop
    location: Sydney

The 'location' parameter should correspond to one of the keys in the RADARS
dict, relow. The configuration validator in the web interface will display a
list of valid names if an incorrect one is specified.

The optional 'name' parameter can be used to set a custom display name for the
component in the web interface.

The optional 'filename' parameter, if specified, will cause the component to
write the animated GIF image to the specified filesystem path each time it is
updated. The component will attempt to create any missing parent directories
leading to the file.

The paramters 'id', 'frames', and 'delta' may be used to override any of the
values in the RADARS dict below. The 'location' and 'id' parameters are
mutually exclusive: You must specify one or the other. The 'frames' parameter
specifies the number of individual radar images to use when constructing the
GIF (the Javascript-based loops BOM provides usually consist of either 4 or
6 frames). The 'delta' parameter specifies the number of seconds between
frames, as available from BOM (usually 360 seconds (6 minutes) for 6-frame
BOM loops, and 600 seconds (10 minutes) for 4-frame loops). If the 'id'
parameter is specified, 'frames' and 'delta' values MUST be provided; if
'location' is specified, 'frames' and 'delta' MAY be provided to override the
default values from the RADARS dict.

"""

import datetime as dt
import io
import logging
import multiprocessing.dummy
import os
import time

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.helpers import config_validation as cv
from voluptuous import All, In, Invalid, Optional
import requests

REQUIREMENTS = ['Pillow==5.4.1']

CONF_DELTA = 'delta'
CONF_FRAMES = 'frames'
CONF_ID = 'id'
CONF_LOC = 'location'
CONF_NAME = 'name'
CONF_OUTFN = 'filename'

RADARS = {
    'Adelaide':        {'id': '643', 'delta': 360, 'frames': 6},
    'Albany':          {'id': '313', 'delta': 600, 'frames': 4},
    'AliceSprings':    {'id': '253', 'delta': 600, 'frames': 4},
    'Bairnsdale':      {'id': '683', 'delta': 600, 'frames': 4},
    'Bowen':           {'id': '243', 'delta': 600, 'frames': 4},
    'Brisbane':        {'id': '663', 'delta': 360, 'frames': 6},
    'Broome':          {'id': '173', 'delta': 600, 'frames': 4},
    'Cairns':          {'id': '193', 'delta': 360, 'frames': 6},
    'Canberra':        {'id': '403', 'delta': 360, 'frames': 6},
    'Carnarvon':       {'id': '053', 'delta': 600, 'frames': 4},
    'Ceduna':          {'id': '333', 'delta': 600, 'frames': 4},
    'Dampier':         {'id': '153', 'delta': 600, 'frames': 4},
    'Darwin':          {'id': '633', 'delta': 360, 'frames': 6},
    'Emerald':         {'id': '723', 'delta': 600, 'frames': 4},
    'Esperance':       {'id': '323', 'delta': 600, 'frames': 4},
    'Geraldton':       {'id': '063', 'delta': 600, 'frames': 4},
    'Giles':           {'id': '443', 'delta': 600, 'frames': 4},
    'Gladstone':       {'id': '233', 'delta': 600, 'frames': 4},
    'Gove':            {'id': '093', 'delta': 600, 'frames': 4},
    'Grafton':         {'id': '283', 'delta': 600, 'frames': 4},
    'Gympie':          {'id': '083', 'delta': 360, 'frames': 6},
    'HallsCreek':      {'id': '393', 'delta': 600, 'frames': 4},
    'Hobart':          {'id': '763', 'delta': 360, 'frames': 6},
    'Kalgoorlie':      {'id': '483', 'delta': 360, 'frames': 6},
    'Katherine':       {'id': '423', 'delta': 360, 'frames': 6},
    'Learmonth':       {'id': '293', 'delta': 600, 'frames': 4},
    'Longreach':       {'id': '563', 'delta': 600, 'frames': 4},
    'Mackay':          {'id': '223', 'delta': 600, 'frames': 4},
    'Marburg':         {'id': '503', 'delta': 600, 'frames': 4},
    'Melbourne':       {'id': '023', 'delta': 360, 'frames': 6},
    'Mildura':         {'id': '303', 'delta': 600, 'frames': 4},
    'Moree':           {'id': '533', 'delta': 600, 'frames': 4},
    'MorningtonIs':    {'id': '363', 'delta': 600, 'frames': 4},
    'MountIsa':        {'id': '753', 'delta': 360, 'frames': 6},
    'MtGambier':       {'id': '143', 'delta': 600, 'frames': 4},
    'Namoi':           {'id': '693', 'delta': 600, 'frames': 4},
    'Newcastle':       {'id': '043', 'delta': 360, 'frames': 6},
    'Newdegate':       {'id': '383', 'delta': 360, 'frames': 6},
    'NorfolkIs':       {'id': '623', 'delta': 600, 'frames': 4},
    'NWTasmania':      {'id': '523', 'delta': 360, 'frames': 6},
    'Perth':           {'id': '703', 'delta': 360, 'frames': 6},
    'PortHedland':     {'id': '163', 'delta': 600, 'frames': 4},
    'SellicksHill':    {'id': '463', 'delta': 600, 'frames': 4},
    'SouthDoodlakine': {'id': '583', 'delta': 360, 'frames': 6},
    'Sydney':          {'id': '713', 'delta': 360, 'frames': 6},
    'Townsville':      {'id': '733', 'delta': 360, 'frames': 6},
    'WaggaWagga':      {'id': '553', 'delta': 600, 'frames': 4},
    'Warrego':         {'id': '673', 'delta': 600, 'frames': 4},
    'Warruwi':         {'id': '773', 'delta': 360, 'frames': 6},
    'Watheroo':        {'id': '793', 'delta': 360, 'frames': 6},
    'Weipa':           {'id': '783', 'delta': 360, 'frames': 6},
    'WillisIs':        {'id': '413', 'delta': 600, 'frames': 4},
    'Wollongong':      {'id': '033', 'delta': 360, 'frames': 6},
    'Woomera':         {'id': '273', 'delta': 600, 'frames': 4},
    'Wyndham':         {'id': '073', 'delta': 600, 'frames': 4},
    'Yarrawonga':      {'id': '493', 'delta': 360, 'frames': 6},
}

locs = sorted(RADARS.keys())
badloc = "Set 'location' to one of: {}".format(', '.join(locs))
logger = logging.getLogger(__name__)

def validate_schema(cfg):
    msg0 = "Specify either 'id' or 'location', not both"
    msg1 = "Specify 'id', 'delta' and 'frames' when 'location' is unspecified"
    if cfg.get('location'):
        if cfg.get('id'):
            raise Invalid(msg0)
    else:
        if not all([cfg.get('id'), cfg.get('delta'), cfg.get('frames')]):
            raise Invalid(msg1)
    return cfg

PLATFORM_SCHEMA = All(PLATFORM_SCHEMA.extend({
    Optional(CONF_DELTA): cv.positive_int,
    Optional(CONF_OUTFN): cv.string,
    Optional(CONF_FRAMES): cv.positive_int,
    Optional(CONF_ID): cv.positive_int,
    Optional(CONF_LOC): All(In(locs), msg=badloc),
    Optional(CONF_NAME): cv.string,
}), validate_schema)


def log(msg):
    logger.debug(msg)


def log_error(msg):
    logger.error(msg)


def setup_platform(hass, config, add_devices, discovery_info=None):
    location = config.get(CONF_LOC)
    if location:
        radar_id = RADARS[location]['id']
        delta = config.get(CONF_DELTA) or RADARS[location]['delta']
        frames = config.get(CONF_FRAMES) or RADARS[location]['frames']
    else:
        radar_id = config.get(CONF_ID)
        delta = config.get(CONF_DELTA)
        frames = config.get(CONF_FRAMES)
        location = "ID {}".format(radar_id)
    name = config.get(CONF_NAME) or "BOM Radar Loop - {}".format(location)
    outfn = config.get(CONF_OUTFN)
    bomradarloop = BOMRadarLoop(hass, location, delta, frames, radar_id, name, outfn)
    add_devices([bomradarloop])


class BOMRadarLoop(Camera):

    def __init__(self, hass, location, delta, frames, radar_id, name, outfn):

        import PIL.Image

        super().__init__()

        self.hass = hass
        self._location = location
        self._delta = delta
        self._frames = frames
        self._radar_id = radar_id
        self._name = name
        self._outfn = outfn

        self._pilimg = PIL.Image
        self._loop = None
        self._t0 = 0

    def camera_image(self):
        now = int(time.time())
        t1 = now - (now % self._delta)
        if t1 > self._t0:
            self._t0 = t1
            self._loop = self.get_loop()
        return self._loop
        
    def get_background(self):

        """
        Fetch the background map, then the topography, locations (e.g. city
        names), and distance-from-radar range markings, and merge into a single
        image.
        """

        log("Getting background for {} at {}".format(self._location, self._t0))
        suffix = 'products/radar_transparencies/IDR{}.background.png'
        url = self.get_url(suffix.format(self._radar_id))
        background = self.get_image(url)
        if background is None:
            return None
        for layer in ('topography', 'locations', 'range'):
            log("Getting {} for {} at {}".format(layer, self._location, self._t0))
            suffix = 'products/radar_transparencies/IDR{}.{}.png'.format(
                self._radar_id,
                layer
            )
            url = self.get_url(suffix)
            image = self.get_image(url)
            if image is not None:
                background = self._pilimg.alpha_composite(background, image)
        return background

    def get_frames(self):

        """
        Use a thread pool to fetch a set of current radar images in parallel,
        then get a background image for this location, combine it with the
        colorbar legend, and finally composite each radar image onto a copy of
        the combined background/legend image.

        The 'wximages' list is created so that requested images that could not
        be fetched are excluded, so that the set of frames will be a best-
        effort set of whatever was actually available at request time. If the
        list is empty, None is returned; the caller can decide how to handle
        that.
        """

        log("Getting frames for {} at {}".format(self._location, self._t0))
        fn_get = lambda time_str: self.get_wximg(time_str)
        pool0 = multiprocessing.dummy.Pool(self._frames)
        raw = pool0.map(fn_get, self.get_time_strs())
        wximages = [x for x in raw if x is not None]
        if not wximages:
            return None
        pool1 = multiprocessing.dummy.Pool(len(wximages))
        background = self.get_background()
        if background is None:
            return None
        fn_composite = lambda x: self._pilimg.alpha_composite(background, x)
        composites = pool1.map(fn_composite, wximages)
        legend = self.get_legend()
        if legend is None:
            return None
        loop_frames = pool1.map(lambda _: legend.copy(), composites)
        fn_paste = lambda x: x[0].paste(x[1], (0, 0))
        pool1.map(fn_paste, zip(loop_frames, composites))
        return loop_frames

    def get_image(self, url):

        """
        Fetch an image from the BOM.
        """

        log("Getting image {}".format(url))
        response = requests.get(url)
        if response.status_code == 200:
            image = self._pilimg.open(io.BytesIO(response.content))
            return image.convert('RGBA')
        return None

    def get_legend(self):

        """
        Fetch the BOM colorbar legend image.
        """

        log("Getting legend at {}".format(self._t0))
        url = self.get_url('products/radar_transparencies/IDR.legend.0.png')
        return self.get_image(url)

    def get_loop(self):

        """
        Return an animated GIF comprising a set of frames, where each frame
        includes a background, one or more supplemental layers, a colorbar
        legend, and a radar image.
        """

        log("Getting loop for {} at {}".format(self._location, self._t0))
        loop = io.BytesIO()
        try:
            frames = self.get_frames()
            if frames is None:
                raise
            log("Got {} frames for {} at {}".format(
                len(frames),
                self._location,
                self._t0
            ))
            frames[0].save(
                loop,
                append_images=frames[1:],
                duration=500,
                format='GIF',
                loop=0,
                save_all=True,
            )
        except:
            log("Got NO frames for {} at {}".format(self._location, self._t0))
            self._pilimg.new('RGB', (340, 370)).save(loop, format='GIF')
        if self._outfn:
            outdir = os.path.dirname(self._outfn)
            if not os.path.isdir(outdir):
                try:
                    os.makedirs(outdir)
                except:
                    log_error("Could not create directory {}".format(outdir))
            try:
                with open(self._outfn, 'wb') as f:
                    f.write(loop.getvalue())
            except:
                log_error("Could not write image to {}".format(self._outfn))
        return loop.getvalue()

    def get_time_strs(self):

        """
        Return a list of strings representing YYYYMMDDHHMM times for the most
        recent set of radar images to be used to create the animated GIF.
        """

        log("Getting time strings starting at {}".format(self._t0))
        tz = dt.timezone.utc
        mkdt = lambda n: dt.datetime.fromtimestamp(
            self._t0 - (self._delta * n),
            tz=tz
        )
        ns = range(self._frames, 0, -1)
        return [mkdt(n).strftime('%Y%m%d%H%M') for n in ns]

    def get_url(self, path):

        """
        Return a canonical URL for a suffix path on the BOM website.
        """

        log("Getting URL for path {}".format(path))
        return 'http://www.bom.gov.au/{}'.format(path)

    def get_wximg(self, time_str):

        """
        Return a radar weather image from the BOM website. Note that
        get_image() returns None if the image could not be fetched, so the
        caller must deal with that possibility.
        """

        log("Getting radar imagery for {} at {}".format(self._location, time_str))
        url = self.get_url(
            '/radar/IDR{}.T.{}.png'.format(self._radar_id, time_str)
        )
        return self.get_image(url)

    @property
    def name(self):
        return self._name
