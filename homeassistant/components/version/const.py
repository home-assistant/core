"""Constants for the Version integration."""

from __future__ import annotations

from datetime import timedelta
from logging import Logger, getLogger
from typing import Any, Final

from pyhaversion.consts import HaVersionChannel, HaVersionSource

from homeassistant.const import CONF_NAME, Platform

DOMAIN: Final = "version"
LOGGER: Final[Logger] = getLogger(__package__)
PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.SENSOR]
UPDATE_COORDINATOR_UPDATE_INTERVAL: Final[timedelta] = timedelta(minutes=5)

ENTRY_TYPE_SERVICE: Final = "service"
HOME_ASSISTANT: Final = "Home Assistant"
POSTFIX_CONTAINER_NAME: Final = "-homeassistant"


CONF_BETA: Final = "beta"
CONF_BOARD: Final = "board"
CONF_CHANNEL: Final = "channel"
CONF_IMAGE: Final = "image"
CONF_VERSION_SOURCE: Final = "version_source"
CONF_SOURCE: Final = "source"

ATTR_CHANNEL: Final = CONF_CHANNEL
ATTR_VERSION_SOURCE: Final = CONF_VERSION_SOURCE
ATTR_SOURCE: Final = CONF_SOURCE

SOURCE_DOCKER: Final = "docker"  # Kept to not break existing configurations

VERSION_SOURCE_DOCKER_HUB: Final = "Docker Hub"
VERSION_SOURCE_HAIO: Final = "Home Assistant Website"
VERSION_SOURCE_LOCAL: Final = "Local installation"
VERSION_SOURCE_PYPI: Final = "Python Package Index (PyPI)"
VERSION_SOURCE_VERSIONS: Final = "Home Assistant Versions"

DEFAULT_BETA: Final = False
DEFAULT_BOARD: Final = "OVA"
DEFAULT_CHANNEL: Final = "stable"
DEFAULT_IMAGE: Final = "default"
DEFAULT_NAME_CURRENT: Final = "Current Version"
DEFAULT_NAME: Final = ""
DEFAULT_SOURCE: Final = "local"
DEFAULT_CONFIGURATION: Final[dict[str, Any]] = {
    CONF_NAME: DEFAULT_NAME,
    CONF_CHANNEL: DEFAULT_CHANNEL,
    CONF_IMAGE: DEFAULT_IMAGE,
    CONF_BOARD: DEFAULT_BOARD,
    CONF_VERSION_SOURCE: VERSION_SOURCE_LOCAL,
    CONF_SOURCE: DEFAULT_SOURCE,
}

STEP_VERSION_SOURCE: Final = "version_source"
STEP_USER: Final = "user"

HA_VERSION_SOURCES: Final[list[str]] = [source.value for source in HaVersionSource]

BOARD_MAP: Final[dict[str, str]] = {
    "OVA": "ova",
    "RaspberryPi 2": "rpi2",
    "RaspberryPi 3": "rpi3",
    "RaspberryPi 3 64bit": "rpi3-64",
    "RaspberryPi 4": "rpi4",
    "RaspberryPi 4 64bit": "rpi4-64",
    "RaspberryPi 5": "rpi5-64",
    "ASUS Tinkerboard": "tinker",
    "ODROID C2": "odroid-c2",
    "ODROID C4": "odroid-c4",
    "ODROID M1": "odroid-m1",
    "ODROID M1S": "odroid-m1s",
    "ODROID N2": "odroid-n2",
    "ODROID XU4": "odroid-xu4",
    "Generic AArch64": "generic-aarch64",
    "Generic x86-64": "generic-x86-64",
    "Home Assistant Yellow": "yellow",
    "Home Assistant Green": "green",
    "Khadas VIM3": "khadas-vim3",
}

VALID_BOARDS: Final[list[str]] = list(BOARD_MAP)

VERSION_SOURCE_MAP: Final[dict[str, str]] = {
    VERSION_SOURCE_LOCAL: "local",
    VERSION_SOURCE_VERSIONS: "supervisor",
    VERSION_SOURCE_HAIO: "haio",
    VERSION_SOURCE_DOCKER_HUB: "container",
    VERSION_SOURCE_PYPI: "pypi",
}

VALID_SOURCES: Final[list[str]] = [
    *HA_VERSION_SOURCES,
    "hassio",  # Kept to not break existing configurations
    "docker",  # Kept to not break existing configurations
]

VALID_IMAGES: Final = [
    "default",
    "generic-x86-64",
    "intel-nuc",
    "odroid-c2",
    "odroid-m1",
    "odroid-n2",
    "odroid-xu",
    "qemuarm-64",
    "qemuarm",
    "qemux86-64",
    "qemux86",
    "raspberrypi",
    "raspberrypi2",
    "raspberrypi3-64",
    "raspberrypi3",
    "raspberrypi4-64",
    "raspberrypi4",
    "raspberrypi5-64",
    "tinker",
]

VALID_CONTAINER_IMAGES: Final[list[str]] = [
    f"{image}{POSTFIX_CONTAINER_NAME}" if image != DEFAULT_IMAGE else image
    for image in VALID_IMAGES
]
VALID_CHANNELS: Final[list[str]] = [
    str(channel.value).title() for channel in HaVersionChannel
]
