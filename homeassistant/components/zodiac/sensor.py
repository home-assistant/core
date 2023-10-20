"""Support for tracking the zodiac sign."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import as_local, utcnow

from .const import (
    ATTR_ELEMENT,
    ATTR_MODALITY,
    DEFAULT_NAME,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the entries."""

    async_add_entities([ZodiacSensor(entry_id=entry.entry_id)], True)


class ZodiacSensor(SensorEntity):
    """Representation of a Zodiac sensor."""

    _attr_name = None
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
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
    ]
    _attr_translation_key = "sign"
    _attr_unique_id = DOMAIN

    def __init__(self, entry_id: str) -> None:
        """Initialize Zodiac sensor."""
        self._attr_device_info = DeviceInfo(
            name=DEFAULT_NAME,
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_update(self) -> None:
        """Get the time and updates the state."""
        today = as_local(utcnow()).date()

        for sign in ZODIAC_BY_DATE:
            if (today.month == sign[0][1] and today.day >= sign[0][0]) or (
                today.month == sign[1][1] and today.day <= sign[1][0]
            ):
                self._attr_native_value = sign[2]
                self._attr_icon = ZODIAC_ICONS.get(sign[2])
                self._attr_extra_state_attributes = sign[3]
                break
