"""Support for tracking the zodiac sign."""
import logging

from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Zodiac"


STATE_ARIES = "aries"
STATE_TAURUS = "taurus"
STATE_GEMINI = "gemini"
STATE_CANCER = "cancer"
STATE_LEO = "leo"
STATE_VIRGO = "virgo"
STATE_LIBRA = "libra"
STATE_SCORPIO = "scorpio"
STATE_SAGITTARIUS = "sagittarius"
STATE_CAPRICORN = "capricorn"
STATE_AQUARIUS = "aquarius"
STATE_PISCES = "pisces"

ZODIAC_BY_DATE = (
    ((20, 3), (19, 4)),  # Aries
    ((20, 4), (20, 5)),
    ((21, 5), (20, 6)),
    ((21, 6), (22, 7)),
    ((23, 7), (22, 8)),
    ((23, 8), (22, 9)),
    ((23, 9), (22, 10)),
    ((23, 10), (21, 11)),
    ((22, 11), (21, 12)),
    ((22, 12), (19, 1)),
    ((20, 1), (17, 2)),
    ((18, 2), (19, 3)),  # Pisces
)

ZODIAC_LIST = {
    0: STATE_ARIES,
    1: STATE_TAURUS,
    2: STATE_GEMINI,
    3: STATE_CANCER,
    4: STATE_LEO,
    5: STATE_VIRGO,
    6: STATE_LIBRA,
    7: STATE_SCORPIO,
    8: STATE_SAGITTARIUS,
    9: STATE_CAPRICORN,
    10: STATE_AQUARIUS,
    11: STATE_PISCES,
}

ZODIAC_ICONS = {
    STATE_ARIES: "mdi:zodiac-aries",
    STATE_TAURUS: "mdi:zodiac-taurus",
    STATE_GEMINI: "mdi:zodiac-gemini",
    STATE_CANCER: "mdi:zodiac-cancer",
    STATE_LEO: "mdi:zodiac-leo",
    STATE_VIRGO: "mdi:zodiac-virgo",
    STATE_LIBRA: "mdi:zodiac-libra",
    STATE_SCORPIO: "mdi:zodiac-scorpio",
    STATE_SAGITTARIUS: "mdi:zodiac-sagittarius",
    STATE_CAPRICORN: "mdi:zodiac-capricorn",
    STATE_AQUARIUS: "mdi:zodiac-aquarius",
    STATE_PISCES: "mdi:zodiac-pisces",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Zodiac sensor platform."""
    async_add_entities([ZodiacSensor()], True)


class ZodiacSensor(Entity):
    """Representation of a Zodiac sensor."""

    def __init__(self):
        """Initialize the zodiac sensor."""
        self._state = None

    @property
    def name(self):
        """Return the name of the entity."""
        return "Zodiac"

    @property
    def device_class(self):
        """Return the device class of the entity."""
        return "zodiac__sign"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ZODIAC_ICONS.get(self.state)

    async def async_update(self):
        """Get the time and updates the states."""
        today = dt_util.as_local(dt_util.utcnow()).date()

        month = int(today.month)
        day = int(today.day)

        for index, sign in enumerate(ZODIAC_BY_DATE):
            if (month == sign[0][1] and day >= sign[0][0]) or (
                month == sign[1][1] and day <= sign[1][0]
            ):
                self._state = ZODIAC_LIST[index]
                break
