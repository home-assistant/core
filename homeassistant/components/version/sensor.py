"""Sensor that can display the current Home Assistant versions."""
from datetime import timedelta

from pyhaversion import HaVersion, HaVersionChannel, HaVersionSource
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, CONF_SOURCE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

ALL_IMAGES = [
    "default",
    "intel-nuc",
    "odroid-c2",
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
    "tinker",
]
ALL_SOURCES = [
    "container",
    "haio",
    "local",
    "pypi",
    "supervisor",
    "hassio",  # Kept to not break existing configurations
    "docker",  # Kept to not break existing configurations
]

CONF_BETA = "beta"
CONF_IMAGE = "image"

DEFAULT_IMAGE = "default"
DEFAULT_NAME_LATEST = "Latest Version"
DEFAULT_NAME_LOCAL = "Current Version"
DEFAULT_SOURCE = "local"

ICON = "mdi:package-up"

TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_BETA, default=False): cv.boolean,
        vol.Optional(CONF_IMAGE, default=DEFAULT_IMAGE): vol.In(ALL_IMAGES),
        vol.Optional(CONF_NAME, default=""): cv.string,
        vol.Optional(CONF_SOURCE, default=DEFAULT_SOURCE): vol.In(ALL_SOURCES),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Version sensor platform."""

    beta = config.get(CONF_BETA)
    image = config.get(CONF_IMAGE)
    name = config.get(CONF_NAME)
    source = config.get(CONF_SOURCE)

    session = async_get_clientsession(hass)

    channel = HaVersionChannel.BETA if beta else HaVersionChannel.STABLE

    if source == "pypi":
        haversion = VersionData(
            HaVersion(session, source=HaVersionSource.PYPI, channel=channel)
        )
    elif source in ["hassio", "supervisor"]:
        haversion = VersionData(
            HaVersion(
                session, source=HaVersionSource.SUPERVISOR, channel=channel, image=image
            )
        )
    elif source in ["docker", "container"]:
        if image is not None and image != DEFAULT_IMAGE:
            image = f"{image}-homeassistant"
        haversion = VersionData(
            HaVersion(
                session, source=HaVersionSource.CONTAINER, channel=channel, image=image
            )
        )
    elif source == "haio":
        haversion = VersionData(HaVersion(session, source=HaVersionSource.HAIO))
    else:
        haversion = VersionData(HaVersion(session, source=HaVersionSource.LOCAL))

    if not name:
        if source == DEFAULT_SOURCE:
            name = DEFAULT_NAME_LOCAL
        else:
            name = DEFAULT_NAME_LATEST

    async_add_entities([VersionSensor(haversion, name)], True)


class VersionData:
    """Get the latest data and update the states."""

    def __init__(self, api: HaVersion):
        """Initialize the data object."""
        self.api = api

    @Throttle(TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest version information."""
        await self.api.get_version()


class VersionSensor(SensorEntity):
    """Representation of a Home Assistant version sensor."""

    def __init__(self, data: VersionData, name: str):
        """Initialize the Version sensor."""
        self.data = data
        self._name = name
        self._state = None

    async def async_update(self):
        """Get the latest version information."""
        await self.data.async_update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.data.api.version

    @property
    def extra_state_attributes(self):
        """Return attributes for the sensor."""
        return self.data.api.version_data

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON
