"""Component that will help set the OpenALPR cloud for ALPR processing."""

import asyncio
from base64 import b64encode
from http import HTTPStatus
import logging
from typing import Any, override

import aiohttp
import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_CONFIDENCE,
    CONF_CONFIDENCE,
    PLATFORM_SCHEMA as IMAGE_PROCESSING_PLATFORM_SCHEMA,
    ImageProcessingDeviceClass,
    ImageProcessingEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    CONF_API_KEY,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REGION,
    CONF_SOURCE,
)
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.async_ import run_callback_threadsafe

_LOGGER = logging.getLogger(__name__)

ATTR_PLATE = "plate"
ATTR_PLATES = "plates"
ATTR_VEHICLES = "vehicles"
ATTR_VEHICLE_DETAILS = "vehicle_details"
ATTR_COLOR = "color"

CONF_VEHICLE_DETAILS = "vehicle_details"

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

PLATFORM_SCHEMA = IMAGE_PROCESSING_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_REGION): vol.All(vol.Lower, vol.In(OPENALPR_REGIONS)),
        vol.Optional(CONF_VEHICLE_DETAILS, default=False): cv.boolean,
    }
)


def _candidate_confidence(candidate: dict[str, Any]) -> float:
    """Coerce a candidate's confidence to float, defaulting to 0.0."""
    try:
        return float(candidate.get("confidence", 0))
    except TypeError, ValueError:
        return 0.0


def _top_candidate(candidates: list[dict[str, Any]] | None) -> str | None:
    """Return the highest confidence candidate's value, if any.

    OpenALPR always returns a full top-10 ranked list even with no real
    signal, with every candidate at confidence 0 in that case. Treat that
    as no detection rather than reporting a meaningless top-of-list guess.
    """
    if not candidates:
        return None
    top = max(candidates, key=_candidate_confidence)
    if _candidate_confidence(top) <= 0:
        return None
    return top.get("value")


def _format_label(value: str | None) -> str | None:
    """Turn a raw OpenALPR value like 'mercedes-benz' into 'Mercedes-Benz'."""
    if not value:
        return None
    return value.replace("_", " ").title()


def _format_model(make_model: str | None, make: str | None) -> str | None:
    """Strip the make prefix from a makemodel slug and prettify it.

    OpenALPR's makemodel task returns values like 'hyundai_sonata'; the make
    is already reported separately, so drop that prefix and keep just the
    model, e.g. 'Sonata'.
    """
    if not make_model:
        return None
    model = make_model
    if make and model.lower().startswith(f"{make.lower()}_"):
        model = model[len(make) + 1 :]
    return _format_label(model)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the OpenALPR cloud API platform."""
    confidence: float = config[CONF_CONFIDENCE]
    source: list[dict[str, str]] = config[CONF_SOURCE]
    include_vehicle_details: bool = config[CONF_VEHICLE_DETAILS]
    tasks = "plate,color,make,makemodel" if include_vehicle_details else "plate"
    params = {
        "secret_key": config[CONF_API_KEY],
        "tasks": tasks,
        "return_image": 0,
        "country": config[CONF_REGION],
    }

    async_add_entities(
        OpenAlprCloudEntity(
            camera[CONF_ENTITY_ID],
            params,
            confidence,
            camera.get(CONF_NAME),
            include_vehicle_details,
        )
        for camera in source
    )


class ImageProcessingAlprEntity(ImageProcessingEntity):
    """Base entity class for ALPR image processing."""

    _attr_device_class = ImageProcessingDeviceClass.ALPR

    def __init__(self, include_vehicle_details: bool = False) -> None:
        """Initialize base ALPR entity."""
        self.plates: dict[str, float] = {}
        self.vehicles = 0
        self._include_vehicle_details = include_vehicle_details
        self.vehicle_details: list[dict[str, Any]] = []

    @property
    @override
    def state(self) -> str | None:
        """Return the state of the entity."""
        confidence = 0.0
        plate: str | None = None

        # search high plate
        for i_pl, i_co in self.plates.items():
            if i_co > confidence:
                confidence = i_co
                plate = i_pl
        return plate

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        attributes: dict[str, Any] = {
            ATTR_PLATES: self.plates,
            ATTR_VEHICLES: self.vehicles,
        }

        if not self._include_vehicle_details:
            return attributes

        attributes[ATTR_VEHICLE_DETAILS] = self.vehicle_details

        # Surface the vehicle details for the currently reported (highest
        # confidence) plate as flat attributes for easy templating.
        for vehicle in self.vehicle_details:
            if vehicle[ATTR_PLATE] == self.state:
                attributes[ATTR_COLOR] = vehicle[ATTR_COLOR]
                attributes[ATTR_MANUFACTURER] = vehicle[ATTR_MANUFACTURER]
                attributes[ATTR_MODEL] = vehicle[ATTR_MODEL]
                break

        return attributes

    def process_plates(
        self,
        plates: dict[str, float],
        vehicles: int,
        vehicle_details: list[dict[str, Any]] | None = None,
    ) -> None:
        """Send event with new plates and store data."""
        run_callback_threadsafe(
            self.hass.loop,
            self.async_process_plates,
            plates,
            vehicles,
            vehicle_details,
        ).result()

    @callback
    def async_process_plates(
        self,
        plates: dict[str, float],
        vehicles: int,
        vehicle_details: list[dict[str, Any]] | None = None,
    ) -> None:
        """Send event with new plates and store data.

        Plates are a dict in follow format:
          { '<plate>': confidence }
        This method must be run in the event loop.
        """
        vehicle_details = vehicle_details or []
        plates = {
            plate: confidence
            for plate, confidence in plates.items()
            if self.confidence is None or confidence >= self.confidence
        }
        new_plates = set(plates) - set(self.plates)

        vehicle_by_plate = {
            vehicle[ATTR_PLATE]: vehicle
            for vehicle in vehicle_details
            if vehicle[ATTR_PLATE] is not None
        }

        # Send events
        for i_plate in new_plates:
            event_data = {
                ATTR_PLATE: i_plate,
                ATTR_ENTITY_ID: self.entity_id,
                ATTR_CONFIDENCE: plates.get(i_plate),
            }

            vehicle = vehicle_by_plate.get(i_plate)
            if vehicle is not None:
                event_data[ATTR_COLOR] = vehicle[ATTR_COLOR]
                event_data[ATTR_MANUFACTURER] = vehicle[ATTR_MANUFACTURER]
                event_data[ATTR_MODEL] = vehicle[ATTR_MODEL]

            self.hass.bus.async_fire(EVENT_FOUND_PLATE, event_data)

        # Update entity store
        self.plates = plates
        self.vehicles = vehicles
        self.vehicle_details = vehicle_details


class OpenAlprCloudEntity(ImageProcessingAlprEntity):
    """Representation of an OpenALPR cloud entity."""

    def __init__(
        self,
        camera_entity: str,
        params: dict[str, Any],
        confidence: float,
        name: str | None,
        include_vehicle_details: bool = False,
    ) -> None:
        """Initialize OpenALPR cloud API."""
        super().__init__(include_vehicle_details)

        self._params = params
        self._attr_camera_entity = camera_entity
        self._attr_confidence = confidence

        if name:
            self._attr_name = name
        else:
            self._attr_name = f"OpenAlpr {split_entity_id(camera_entity)[1]}"

    @override
    async def async_process_image(self, image: bytes) -> None:
        """Process image.

        This method is a coroutine.
        """
        websession = async_get_clientsession(self.hass)
        params = self._params.copy()

        body = {"image_bytes": str(b64encode(image), "utf-8")}

        try:
            async with asyncio.timeout(self.timeout):
                request = await websession.post(
                    OPENALPR_API_URL, params=params, data=body
                )

                data = await request.json()

                if request.status != HTTPStatus.OK:
                    _LOGGER.error("Error %d -> %s", request.status, data.get("error"))
                    return

        except TimeoutError, aiohttp.ClientError:
            _LOGGER.error("Timeout for OpenALPR API")
            return

        # Processing API data
        vehicles = 0
        result: dict[str, float] = {}
        vehicle_details: list[dict[str, Any]] = []

        for row in data["plate"]["results"]:
            vehicles += 1

            for p_data in row["candidates"]:
                try:
                    p_confidence = float(p_data["confidence"])
                except ValueError:
                    continue

                result[p_data["plate"]] = p_confidence

        best_plate: str | None = None
        best_confidence = 0.0
        for plate, plate_confidence in result.items():
            if plate_confidence > best_confidence:
                best_confidence = plate_confidence
                best_plate = plate

        # OpenALPR reports color/make/makemodel once per image, not once per
        # detected plate, so attach it to whichever plate is reported as the
        # entity's state (the highest confidence one).
        if self._include_vehicle_details and best_plate is not None:
            raw_make = _top_candidate(data.get("make"))
            vehicle_details.append(
                {
                    ATTR_PLATE: best_plate,
                    ATTR_CONFIDENCE: best_confidence,
                    ATTR_COLOR: _format_label(_top_candidate(data.get("color"))),
                    ATTR_MANUFACTURER: _format_label(raw_make),
                    ATTR_MODEL: _format_model(
                        _top_candidate(data.get("makemodel")), raw_make
                    ),
                }
            )

        self.async_process_plates(result, vehicles, vehicle_details)
