"""Component that will help set the OpenALPR cloud for ALPR processing."""
from __future__ import annotations

import asyncio
from base64 import b64encode
from http import HTTPStatus
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_CONFIDENCE,
    CONF_CONFIDENCE,
    PLATFORM_SCHEMA,
    ImageProcessingDeviceClass,
    ImageProcessingEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_API_KEY,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REGION,
    CONF_SOURCE,
)
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.async_ import run_callback_threadsafe

_LOGGER = logging.getLogger(__name__)

ATTR_PLATE = "plate"
ATTR_PLATES = "plates"
ATTR_VEHICLES = "vehicles"

EVENT_FOUND_PLATE = "image_processing.found_plate"

OPENALPR_API_URL = "https://api.openalpr.com/v1/recognize"

OPENALPR_REGIONS = [
    "au",
    "auwide",
    "br",
    "eu",
    "fr",
    "gb",
    "kr",
    "kr2",
    "mx",
    "sg",
    "us",
    "vn2",
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_REGION): vol.All(vol.Lower, vol.In(OPENALPR_REGIONS)),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the OpenALPR cloud API platform."""
    confidence = config[CONF_CONFIDENCE]
    params = {
        "secret_key": config[CONF_API_KEY],
        "tasks": "plate",
        "return_image": 0,
        "country": config[CONF_REGION],
    }

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(
            OpenAlprCloudEntity(
                camera[CONF_ENTITY_ID], params, confidence, camera.get(CONF_NAME)
            )
        )

    async_add_entities(entities)


class ImageProcessingAlprEntity(ImageProcessingEntity):
    """Base entity class for ALPR image processing."""

    _attr_device_class = ImageProcessingDeviceClass.ALPR

    def __init__(self) -> None:
        """Initialize base ALPR entity."""
        self.plates: dict[str, float] = {}
        self.vehicles = 0

    @property
    def state(self):
        """Return the state of the entity."""
        confidence = 0
        plate = None

        # search high plate
        for i_pl, i_co in self.plates.items():
            if i_co > confidence:
                confidence = i_co
                plate = i_pl
        return plate

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {ATTR_PLATES: self.plates, ATTR_VEHICLES: self.vehicles}

    def process_plates(self, plates: dict[str, float], vehicles: int) -> None:
        """Send event with new plates and store data."""
        run_callback_threadsafe(
            self.hass.loop, self.async_process_plates, plates, vehicles
        ).result()

    @callback
    def async_process_plates(self, plates: dict[str, float], vehicles: int) -> None:
        """Send event with new plates and store data.

        Plates are a dict in follow format:
          { '<plate>': confidence }
        This method must be run in the event loop.
        """
        plates = {
            plate: confidence
            for plate, confidence in plates.items()
            if self.confidence is None or confidence >= self.confidence
        }
        new_plates = set(plates) - set(self.plates)

        # Send events
        for i_plate in new_plates:
            self.hass.async_add_job(
                self.hass.bus.async_fire,
                EVENT_FOUND_PLATE,
                {
                    ATTR_PLATE: i_plate,
                    ATTR_ENTITY_ID: self.entity_id,
                    ATTR_CONFIDENCE: plates.get(i_plate),
                },
            )

        # Update entity store
        self.plates = plates
        self.vehicles = vehicles


class OpenAlprCloudEntity(ImageProcessingAlprEntity):
    """Representation of an OpenALPR cloud entity."""

    def __init__(self, camera_entity, params, confidence, name=None):
        """Initialize OpenALPR cloud API."""
        super().__init__()

        self._params = params
        self._camera = camera_entity
        self._confidence = confidence

        if name:
            self._name = name
        else:
            self._name = f"OpenAlpr {split_entity_id(camera_entity)[1]}"

    @property
    def confidence(self):
        """Return minimum confidence for send events."""
        return self._confidence

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        websession = async_get_clientsession(self.hass)
        params = self._params.copy()

        body = {"image_bytes": str(b64encode(image), "utf-8")}

        try:
            async with async_timeout.timeout(self.timeout):
                request = await websession.post(
                    OPENALPR_API_URL, params=params, data=body
                )

                data = await request.json()

                if request.status != HTTPStatus.OK:
                    _LOGGER.error("Error %d -> %s", request.status, data.get("error"))
                    return

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout for OpenALPR API")
            return

        # Processing API data
        vehicles = 0
        result = {}

        for row in data["plate"]["results"]:
            vehicles += 1

            for p_data in row["candidates"]:
                try:
                    result.update({p_data["plate"]: float(p_data["confidence"])})
                except ValueError:
                    continue

        self.async_process_plates(result, vehicles)
