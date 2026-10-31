"""Provides functionality to interact with image processing services."""

from datetime import timedelta
import logging

import probatio

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_AGE,
    ATTR_CONFIDENCE,
    ATTR_FACES,
    ATTR_GENDER,
    ATTR_GLASSES,
    ATTR_MOTION,
    ATTR_TOTAL_FACES,
    CONF_CONFIDENCE,
    DATA_COMPONENT,
    DEFAULT_CONFIDENCE,
    DOMAIN,
    EVENT_DETECT_FACE,
    SERVICE_SCAN,
    ImageProcessingDeviceClass,
    ImageProcessingEntityStateAttribute,
    ImageProcessingService,
)
from .entity import (
    FaceInformation,
    ImageProcessingEntity,
    ImageProcessingEntityDescription,
    ImageProcessingFaceEntity,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


SOURCE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ENTITY_ID): cv.entity_domain("camera"),
        probatio.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_SOURCE): probatio.All(
            probatio.EnsureList(), [SOURCE_SCHEMA]
        ),
        probatio.Optional(CONF_CONFIDENCE, default=DEFAULT_CONFIDENCE): probatio.All(
            probatio.Coerce(float), probatio.Percentage()
        ),
    }
)
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE.extend(PLATFORM_SCHEMA.schema)

__all__ = [
    "ATTR_AGE",
    "ATTR_CONFIDENCE",
    "ATTR_FACES",
    "ATTR_GENDER",
    "ATTR_GLASSES",
    "ATTR_MOTION",
    "ATTR_TOTAL_FACES",
    "CONF_CONFIDENCE",
    "DEFAULT_CONFIDENCE",
    "DOMAIN",
    "EVENT_DETECT_FACE",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_SCAN",
    "FaceInformation",
    "ImageProcessingDeviceClass",
    "ImageProcessingEntity",
    "ImageProcessingEntityDescription",
    "ImageProcessingEntityStateAttribute",
    "ImageProcessingFaceEntity",
    "ImageProcessingService",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the image processing."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[ImageProcessingEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    async_setup_services(hass)

    return True
