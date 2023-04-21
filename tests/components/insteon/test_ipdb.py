"""Test the Insteon Product Database (IPDB)."""
import logging

from pyinsteon.address import Address
from pyinsteon.device_types.ipdb import (
    DimmableLightingControl_FanLinc,
    DimmableLightingControl_KeypadLinc_6,
    SensorsActuators_IOLink,
)

from homeassistant.components.insteon.ipdb import (
    get_device_config_plaforms,
    get_device_config_platform_props,
    get_device_platform_groups,
    get_device_platforms,
)
from homeassistant.const import Platform

_LOGGER = logging.getLogger(__name__)

devices = [
    DimmableLightingControl_FanLinc(Address("1a1a1a"), 0x01, 0x01),
    DimmableLightingControl_KeypadLinc_6(Address("2b2b2b"), 0x01, 0x02),
    SensorsActuators_IOLink(Address("3c3c3c"), 0x01, 0x03),
]


def test_get_device_platforms() -> None:
    """Get the platforms associated with an Insteon device."""
    platforms0 = [Platform.LIGHT, Platform.FAN]
    platforms1 = [Platform.LIGHT, Platform.SWITCH]
    platforms2 = [Platform.BINARY_SENSOR, Platform.SWITCH]

    for device, platforms in (
        (devices[0], platforms0),
        (devices[1], platforms1),
        (devices[2], platforms2),
    ):
        device_platforms = get_device_platforms(device)
        for platform in platforms:
            assert platform in device_platforms
        for platform in device_platforms:
            assert platform in platforms


def test_get_device_platform_groups() -> None:
    """Test getting the device platform groups."""

    for device, platform, groups in (
        (devices[0], Platform.LIGHT, [1]),
        (devices[0], Platform.FAN, [2]),
        (devices[1], Platform.LIGHT, [1]),
        (devices[1], Platform.SWITCH, [3, 4, 5, 6]),
        (devices[2], Platform.SWITCH, [1]),
        (devices[2], Platform.BINARY_SENSOR, [2]),
    ):
        device_platform_groups = get_device_platform_groups(device, platform)
        for group in device_platform_groups:
            assert group in groups
        for group in groups:
            assert group in device_platform_groups


def test_get_device_config_platforms() -> None:
    """Get the platforms associated with an Insteon device."""
    platforms0 = [Platform.SWITCH, Platform.LIGHT, Platform.SELECT]
    platforms1 = [Platform.LIGHT, Platform.SWITCH, Platform.LIGHT, Platform.SELECT]
    platforms2 = [Platform.SWITCH, Platform.SELECT, Platform.NUMBER]

    for device, platforms in (
        (devices[0], platforms0),
        (devices[1], platforms1),
        (devices[2], platforms2),
    ):
        device_platforms = get_device_config_plaforms(device)
        for platform in platforms:
            assert platform in device_platforms
        for platform in device_platforms:
            assert platform in platforms


def test_get_device_config_platform_props() -> None:
    """Test getting the device configuration platform property names."""

    for device, platform, name_count in (
        (devices[0], Platform.SWITCH, 10),
        (devices[0], Platform.LIGHT, 1),
        (devices[1], Platform.LIGHT, 1),
        (devices[1], Platform.SWITCH, 8),
        (devices[1], Platform.SELECT, 5),
        (devices[2], Platform.SWITCH, 4),
        (devices[2], Platform.SELECT, 1),
        (devices[2], Platform.NUMBER, 1),
    ):
        device_platform_props = get_device_config_platform_props(device, platform)
        assert len(device_platform_props) == name_count
