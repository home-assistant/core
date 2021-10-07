"""Sensor that can display the current Home Assistant versions."""
from datetime import timedelta
import logging

from pyhaversion import (
    HaVersion,
    HaVersionChannel,
    HaVersionSource,
    exceptions as pyhaversionexceptions,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_NAME, CONF_SOURCE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

ALL_IMAGES = [
    "default",
    "generic-x86-64",
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

HA_VERSION_SOURCES = [source.value for source in HaVersionSource]

ALL_SOURCES = HA_VERSION_SOURCES + [
    "hassio",  # Kept to not break existing configurations
    "docker",  # Kept to not break existing configurations
]

CONF_BETA = "beta"
CONF_IMAGE = "image"

DEFAULT_IMAGE = "default"
DEFAULT_NAME_LATEST = "Latest Version"
DEFAULT_NAME_LOCAL = "Current Version"
DEFAULT_SOURCE = "local"

TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_BETA, default=False): cv.boolean,
        vol.Optional(CONF_IMAGE, default=DEFAULT_IMAGE): vol.In(ALL_IMAGES),
        vol.Optional(CONF_NAME, default=""): cv.string,
        vol.Optional(CONF_SOURCE, default=DEFAULT_SOURCE): vol.In(ALL_SOURCES),
    }
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Version sensor platform."""

    beta = config.get(CONF_BETA)
    image = config.get(CONF_IMAGE)
    name = config.get(CONF_NAME)
    source = config.get(CONF_SOURCE)

    channel = HaVersionChannel.BETA if beta else HaVersionChannel.STABLE
    session = async_get_clientsession(hass)

    if source in HA_VERSION_SOURCES:
        source = HaVersionSource(source)
    elif source == "hassio":
        source = HaVersionSource.SUPERVISOR
    elif source == "docker":
        source = HaVersionSource.CONTAINER

    if (
        source == HaVersionSource.CONTAINER
        and image is not None
        and image != DEFAULT_IMAGE
    ):
        image = f"{image}-homeassistant"

    if not (name := config.get(CONF_NAME)):
        if source == HaVersionSource.LOCAL:
            name = DEFAULT_NAME_LOCAL
        else:
            name = DEFAULT_NAME_LATEST

    async_add_entities(
        [
            VersionSensor(
                VersionData(
                    HaVersion(
                        session=session, source=source, image=image, channel=channel
                    )
                ),
                SensorEntityDescription(key=source, name=name),
            )
        ],
        True,
    )


class VersionData:
    """Get the latest data and update the states."""

    def __init__(self, api: HaVersion) -> None:
        """Initialize the data object."""
        self.api = api

    @Throttle(TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest version information."""
        try:
            await self.api.get_version()
        except pyhaversionexceptions.HaVersionFetchException as exception:
            _LOGGER.warning(exception)
        except pyhaversionexceptions.HaVersionParseException as exception:
            _LOGGER.warning(
                "Could not parse data received for %s - %s", self.api.source, exception
            )


class VersionSensor(SensorEntity):
    """Representation of a Home Assistant version sensor."""

    _attr_icon = "mdi:package-up"

    def __init__(
        self,
        data: VersionData,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Version sensor."""
        self.data = data
        self.entity_description = description

    async def async_update(self):
        """Get the latest version information."""
        await self.data.async_update()
        self._attr_native_value = self.data.api.version
        self._attr_extra_state_attributes = self.data.api.version_data
