"""Provide animated GIF loops of BOM radar imagery."""
from bomradarloop import BOMRadarLoop
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.helpers import config_validation as cv

CONF_DELTA = "delta"
CONF_FRAMES = "frames"
CONF_LOCATION = "location"
CONF_OUTFILE = "filename"

LOCATIONS = [
    "Adelaide",
    "Albany",
    "AliceSprings",
    "Bairnsdale",
    "Bowen",
    "Brisbane",
    "Broome",
    "Cairns",
    "Canberra",
    "Carnarvon",
    "Ceduna",
    "Dampier",
    "Darwin",
    "Emerald",
    "Esperance",
    "Geraldton",
    "Giles",
    "Gladstone",
    "Gove",
    "Grafton",
    "Gympie",
    "HallsCreek",
    "Hobart",
    "Kalgoorlie",
    "Katherine",
    "Learmonth",
    "Longreach",
    "Mackay",
    "Marburg",
    "Melbourne",
    "Mildura",
    "Moree",
    "MorningtonIs",
    "MountIsa",
    "MtGambier",
    "Namoi",
    "Newcastle",
    "Newdegate",
    "NorfolkIs",
    "NWTasmania",
    "Perth",
    "PortHedland",
    "Rainbow",
    "SellicksHill",
    "SouthDoodlakine",
    "Sydney",
    "Townsville",
    "WaggaWagga",
    "Warrego",
    "Warruwi",
    "Watheroo",
    "Weipa",
    "WillisIs",
    "Wollongong",
    "Woomera",
    "Wyndham",
    "Yarrawonga",
]


def _validate_schema(config):
    if config.get(CONF_LOCATION) is None:
        if not all(config.get(x) for x in (CONF_ID, CONF_DELTA, CONF_FRAMES)):
            raise vol.Invalid(
                f"Specify '{CONF_ID}', '{CONF_DELTA}' and '{CONF_FRAMES}' when '{CONF_LOCATION}' is unspecified"
            )
    return config


LOCATIONS_MSG = f"Set '{CONF_LOCATION}' to one of: {', '.join(sorted(LOCATIONS))}"
XOR_MSG = f"Specify exactly one of '{CONF_ID}' or '{CONF_LOCATION}'"

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Exclusive(CONF_ID, "xor", msg=XOR_MSG): cv.string,
            vol.Exclusive(CONF_LOCATION, "xor", msg=XOR_MSG): vol.In(
                LOCATIONS, msg=LOCATIONS_MSG
            ),
            vol.Optional(CONF_DELTA): cv.positive_int,
            vol.Optional(CONF_FRAMES): cv.positive_int,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_OUTFILE): cv.string,
        }
    ),
    _validate_schema,
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up BOM radar-loop camera component."""
    location = config.get(CONF_LOCATION) or f"ID {config.get(CONF_ID)}"
    name = config.get(CONF_NAME) or f"BOM Radar Loop - {location}"
    args = [
        config.get(x)
        for x in (CONF_LOCATION, CONF_ID, CONF_DELTA, CONF_FRAMES, CONF_OUTFILE)
    ]
    add_entities([BOMRadarCam(name, *args)])


class BOMRadarCam(Camera):
    """A camera component producing animated BOM radar-imagery GIFs."""

    def __init__(self, name, location, radar_id, delta, frames, outfile):
        """Initialize the component."""

        super().__init__()
        self._name = name
        self._cam = BOMRadarLoop(location, radar_id, delta, frames, outfile)

    def camera_image(self):
        """Return the current BOM radar-loop image."""
        return self._cam.current

    @property
    def name(self):
        """Return the component name."""
        return self._name
