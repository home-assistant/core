"""Support for tracking the zodiac sign."""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import as_local, utcnow

from .const import (
    ATTR_ELEMENT,
    ATTR_MODALITY,
    DOMAIN,
    ELEMENT_AIR,
    ELEMENT_EARTH,
    ELEMENT_FIRE,
    ELEMENT_WATER,
    MODALITY_CARDINAL,
    MODALITY_FIXED,
    MODALITY_MUTABLE,
    SIGN_AQUARIUS,
    SIGN_ARIES,
    SIGN_CANCER,
    SIGN_CAPRICORN,
    SIGN_GEMINI,
    SIGN_LEO,
    SIGN_LIBRA,
    SIGN_PISCES,
    SIGN_SAGITTARIUS,
    SIGN_SCORPIO,
    SIGN_TAURUS,
    SIGN_VIRGO,
)

_LOGGER = logging.getLogger(__name__)

ZODIAC_BY_DATE = (
    (
        (21, 3),
        (20, 4),
        SIGN_ARIES,
        {
            ATTR_ELEMENT: ELEMENT_FIRE,
            ATTR_MODALITY: MODALITY_CARDINAL,
        },
    ),
    (
        (21, 4),
        (20, 5),
        SIGN_TAURUS,
        {
            ATTR_ELEMENT: ELEMENT_EARTH,
            ATTR_MODALITY: MODALITY_FIXED,
        },
    ),
    (
        (21, 5),
        (21, 6),
        SIGN_GEMINI,
        {
            ATTR_ELEMENT: ELEMENT_AIR,
            ATTR_MODALITY: MODALITY_MUTABLE,
        },
    ),
    (
        (22, 6),
        (22, 7),
        SIGN_CANCER,
        {
            ATTR_ELEMENT: ELEMENT_WATER,
            ATTR_MODALITY: MODALITY_CARDINAL,
        },
    ),
    (
        (23, 7),
        (22, 8),
        SIGN_LEO,
        {
            ATTR_ELEMENT: ELEMENT_FIRE,
            ATTR_MODALITY: MODALITY_FIXED,
        },
    ),
    (
        (23, 8),
        (21, 9),
        SIGN_VIRGO,
        {
            ATTR_ELEMENT: ELEMENT_EARTH,
            ATTR_MODALITY: MODALITY_MUTABLE,
        },
    ),
    (
        (22, 9),
        (22, 10),
        SIGN_LIBRA,
        {
            ATTR_ELEMENT: ELEMENT_AIR,
            ATTR_MODALITY: MODALITY_CARDINAL,
        },
    ),
    (
        (23, 10),
        (22, 11),
        SIGN_SCORPIO,
        {
            ATTR_ELEMENT: ELEMENT_WATER,
            ATTR_MODALITY: MODALITY_FIXED,
        },
    ),
    (
        (23, 11),
        (21, 12),
        SIGN_SAGITTARIUS,
        {
            ATTR_ELEMENT: ELEMENT_FIRE,
            ATTR_MODALITY: MODALITY_MUTABLE,
        },
    ),
    (
        (22, 12),
        (20, 1),
        SIGN_CAPRICORN,
        {
            ATTR_ELEMENT: ELEMENT_EARTH,
            ATTR_MODALITY: MODALITY_CARDINAL,
        },
    ),
    (
        (21, 1),
        (19, 2),
        SIGN_AQUARIUS,
        {
            ATTR_ELEMENT: ELEMENT_AIR,
            ATTR_MODALITY: MODALITY_FIXED,
        },
    ),
    (
        (20, 2),
        (20, 3),
        SIGN_PISCES,
        {
            ATTR_ELEMENT: ELEMENT_WATER,
            ATTR_MODALITY: MODALITY_MUTABLE,
        },
    ),
)

ZODIAC_ICONS = {
    SIGN_ARIES: "mdi:zodiac-aries",
    SIGN_TAURUS: "mdi:zodiac-taurus",
    SIGN_GEMINI: "mdi:zodiac-gemini",
    SIGN_CANCER: "mdi:zodiac-cancer",
    SIGN_LEO: "mdi:zodiac-leo",
    SIGN_VIRGO: "mdi:zodiac-virgo",
    SIGN_LIBRA: "mdi:zodiac-libra",
    SIGN_SCORPIO: "mdi:zodiac-scorpio",
    SIGN_SAGITTARIUS: "mdi:zodiac-sagittarius",
    SIGN_CAPRICORN: "mdi:zodiac-capricorn",
    SIGN_AQUARIUS: "mdi:zodiac-aquarius",
    SIGN_PISCES: "mdi:zodiac-pisces",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Zodiac sensor platform."""
    if discovery_info is None:
        return

    async_add_entities([ZodiacSensor()], True)


class ZodiacSensor(Entity):
    """Representation of a Zodiac sensor."""

    def __init__(self):
        """Initialize the zodiac sensor."""
        self._attrs = None
        self._state = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return DOMAIN

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
        return ZODIAC_ICONS.get(self._state)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    async def async_update(self):
        """Get the time and updates the state."""
        today = as_local(utcnow()).date()

        month = int(today.month)
        day = int(today.day)

        for sign in ZODIAC_BY_DATE:
            if (month == sign[0][1] and day >= sign[0][0]) or (
                month == sign[1][1] and day <= sign[1][0]
            ):
                self._state = sign[2]
                self._attrs = sign[3]
                break
