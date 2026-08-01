"""Support for LIFX."""

from ipaddress import ip_address
import re
from socket import gethostbyname
from typing import TYPE_CHECKING, Any, TypedDict

from lifx import HSBK, Colors, LifxError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import color as color_util

from .const import CONF_SERIAL, DOMAIN, LOGGER

if TYPE_CHECKING:
    from .coordinator import LIFXConfigEntry

_SERIAL_PATTERN = re.compile(
    r"(?:[0-9a-f]{12}|(?:[0-9a-f]{2}:){5}[0-9a-f]{2})", re.IGNORECASE
)


def normalize_serial(value: str) -> str:
    """Return a raw twelve-character LIFX protocol serial."""
    if not isinstance(value, str) or _SERIAL_PATTERN.fullmatch(value) is None:
        raise ValueError(f"Invalid LIFX serial: {value}")
    return value.replace(":", "").lower()


async def async_resolve_host(hass: HomeAssistant, host: str) -> str:
    """Return the literal address of a host, which the library requires."""
    try:
        ip_address(host)
    except ValueError:
        return await hass.async_add_executor_job(gethostbyname, host)
    return host


@callback
def async_entry_serial(entry: LIFXConfigEntry) -> str | None:
    """Return a raw serial for an entry of either version, if it holds one."""
    serial = entry.data.get(CONF_SERIAL, entry.unique_id) or ""
    try:
        return normalize_serial(serial)
    except ValueError:
        return None


class HSBKChanges(TypedDict):
    """Color components requested by a Home Assistant service call."""

    hue: float | None
    saturation: float | None
    brightness: float | None
    kelvin: int | None


def parse_hsbk_changes(**kwargs: Any) -> HSBKChanges:
    """Return the public-unit color components a service call asks to change."""
    hue: float | None = None
    saturation: float | None = None
    brightness: float | None = None
    kelvin: int | None = None

    if (color_name := kwargs.get(ATTR_COLOR_NAME)) is not None:
        try:
            hue, saturation = color_util.color_RGB_to_hs(
                *color_util.color_name_to_rgb(color_name)
            )
        except ValueError:
            LOGGER.warning(
                "Got unknown color %s, falling back to neutral white", color_name
            )
            hue, saturation = (0.0, 0.0)

    if ATTR_HS_COLOR in kwargs:
        hue, saturation = kwargs[ATTR_HS_COLOR]
    elif ATTR_RGB_COLOR in kwargs:
        hue, saturation = color_util.color_RGB_to_hs(*kwargs[ATTR_RGB_COLOR])
    elif ATTR_XY_COLOR in kwargs:
        hue, saturation = color_util.color_xy_to_hs(*kwargs[ATTR_XY_COLOR])

    if hue is not None:
        assert saturation is not None
        saturation /= 100
        kelvin = Colors.WHITE_NEUTRAL.kelvin

    if ATTR_COLOR_TEMP_KELVIN in kwargs:
        kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
        saturation = 0.0

    if ATTR_BRIGHTNESS in kwargs:
        brightness = kwargs[ATTR_BRIGHTNESS] / 255
    elif ATTR_BRIGHTNESS_PCT in kwargs:
        brightness = kwargs[ATTR_BRIGHTNESS_PCT] / 100

    return HSBKChanges(
        hue=hue, saturation=saturation, brightness=brightness, kelvin=kelvin
    )


def device_error(err: LifxError) -> HomeAssistantError:
    """Return the error to raise when a device rejects or ignores a command."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="device_error",
        translation_placeholders={"error": str(err)},
    )


def replace_hsbk(base: HSBK, changes: HSBKChanges) -> HSBK:
    """Apply requested changes to a color, rejecting values the device cannot take."""
    try:
        return base.replace(**changes)
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_color",
            translation_placeholders={"error": str(err)},
        ) from err


def overwrites_existing_color(changes: HSBKChanges) -> bool:
    """Return whether a change leaves nothing of the color it is applied to.

    Such a change does not depend on what was there before, so the device does
    not have to be read first. Hue only has to be given when the result ends up
    saturated enough to show it.
    """
    return (
        changes["brightness"] is not None
        and changes["saturation"] is not None
        and changes["kelvin"] is not None
        and (changes["hue"] is not None or changes["saturation"] == 0)
    )


def find_hsbk(base: HSBK, **kwargs: Any) -> HSBK | None:
    """Return a requested color merged onto a base color, or None if unchanged."""
    changes = parse_hsbk_changes(**kwargs)
    if all(value is None for value in changes.values()):
        return None
    return replace_hsbk(base, changes)
