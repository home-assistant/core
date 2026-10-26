"""Helper functions for Philips Hue v2."""

from aiohue.v2 import HueBridgeV2
from aiohue.v2.models.motion_area_configuration import MotionAreaConfiguration

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import color as color_util

from ..const import DOMAIN


def normalize_hue_brightness(brightness: float | None) -> float | None:
    """Return calculated brightness values."""
    if brightness is not None:
        # Hue uses a range of [0, 100] to control brightness.
        brightness = float((brightness / 255) * 100)

    return brightness


def normalize_hue_transition(transition: float | None) -> float | None:
    """Return rounded transition values."""
    if transition is not None:
        # hue transition duration is in milliseconds and round them to 100ms
        transition = int(round(transition, 1) * 1000)

    return transition


def normalize_hue_colortemp(
    colortemp_k: int | None, min_mireds: int, max_mireds: int
) -> int | None:
    """Return color temperature within Hue's ranges."""
    if colortemp_k is None:
        return None
    colortemp_mireds = color_util.color_temperature_kelvin_to_mired(colortemp_k)
    # Hue only accepts a range between min_mireds..max_mireds
    return min(max(colortemp_mireds, min_mireds), max_mireds)


def get_motion_area_device_info(
    api: HueBridgeV2, motion_area: MotionAreaConfiguration
) -> DeviceInfo:
    """Return the device the entities of a MotionAware zone belong to.

    Rooms and zones each have a device of their own. A MotionAware zone that
    covers the whole home points at `bridge_home` instead, which has none, so
    its entities are attached to the bridge.
    """
    if (group := api.groups.get(motion_area.group.rid)) is None:
        return DeviceInfo(identifiers={(DOMAIN, api.config.bridge_id)})
    return DeviceInfo(identifiers={(DOMAIN, group.id)})
