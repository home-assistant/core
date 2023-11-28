"""The viam integration."""
from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from PIL import Image
from viam.app.app_client import RobotPart
from viam.app.viam_client import ViamClient
from viam.robot.client import RobotClient
from viam.rpc.dial import Credentials, DialOptions
from viam.services.vision import VisionClient
from viam.services.vision.client import RawImage
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

DATA_CAPTURE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("values"): vol.All(dict),
        vol.Required("component_name"): vol.All(str),
        vol.Required("component_type", default="sensor"): vol.All(str),
    }
)

IMAGE_SERVICE_FIELDS = {
    vol.Optional("filepath"): vol.All(str, vol.IsFile),
    vol.Optional("camera"): vol.All(str),
}
VISION_SERVICE_FIELDS = {
    vol.Optional("confidence", default="0.6"): vol.All(
        str, vol.Coerce(float), vol.Range(min=0, max=1)
    ),
    vol.Optional("robot_address"): vol.All(str),
    vol.Optional("robot_secret"): vol.All(str),
}

CAPTURE_IMAGE_SERVICE_SCHEMA = vol.Schema(
    {
        **IMAGE_SERVICE_FIELDS,
        vol.Optional("file_name", default="camera"): vol.All(str),
        vol.Optional("component_name"): vol.All(str),
    }
)

CLASSIFICATION_SERVICE_SCHEMA = vol.Schema(
    {
        **IMAGE_SERVICE_FIELDS,
        **VISION_SERVICE_FIELDS,
        vol.Required("classifier_name"): vol.All(str),
        vol.Optional("count", default="2"): vol.All(str, vol.Coerce(int)),
    }
)

DETECTIONS_SERVICE_SCHEMA = vol.Schema(
    {
        **IMAGE_SERVICE_FIELDS,
        **VISION_SERVICE_FIELDS,
        vol.Required("detector_name"): vol.All(str),
    }
)


class ViamManager:
    """Manage Viam client and entry data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ViamClient,
        entry_id: str,
        data: dict[str, Any],
    ) -> None:
        """Store initialized client and user input data."""
        self.hass = hass
        self.client = client
        self.data = data
        self.entry_id = entry_id

    def register_services(self) -> None:
        """Register all available services provided by the integration."""
        self.hass.services.async_register(
            DOMAIN, "capture_data", self.capture_data, DATA_CAPTURE_SERVICE_SCHEMA
        )
        self.hass.services.async_register(
            DOMAIN, "capture_image", self.capture_image, CAPTURE_IMAGE_SERVICE_SCHEMA
        )
        self.hass.services.async_register(
            DOMAIN,
            "get_classifications",
            self.get_classifications,
            CLASSIFICATION_SERVICE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
        self.hass.services.async_register(
            DOMAIN,
            "get_detections",
            self.get_detections,
            DETECTIONS_SERVICE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    def unload(self) -> None:
        """Clean up any open clients."""
        self.hass.services.remove(DOMAIN, "capture_data")
        self.hass.services.remove(DOMAIN, "capture_image")
        self.hass.services.remove(DOMAIN, "get_classifications")
        self.hass.services.remove(DOMAIN, "get_detections")
        self.client.close()

    async def capture_data(self, call: ServiceCall) -> None:
        """Accept input from service call to send to Viam."""
        parts: list[RobotPart] = await self.client.app_client.get_robot_parts(
            robot_id=self.data["robot_id"]
        )
        values = [call.data.get("values")]
        component_type = call.data.get("component_type", "sensor")
        component_name = call.data.get("component_name")

        await self.client.data_client.tabular_data_capture_upload(
            tabular_data=values,
            part_id=parts.pop().id,
            component_type=component_type,
            component_name=component_name,
            method_name="capture_data",
            data_request_times=[(datetime.now(), datetime.now())],
        )

    async def capture_image(self, call: ServiceCall) -> None:
        """Accept input from service call to send to Viam."""
        parts: list[RobotPart] = await self.client.app_client.get_robot_parts(
            robot_id=self.data["robot_id"]
        )
        filepath = call.data.get("filepath")
        camera = call.data.get("camera")
        component_name = call.data.get("component_name")
        file_name = call.data.get("file_name", "camera")

        if filepath is not None:
            await self.client.data_client.file_upload_from_path(
                filepath=filepath,
                part_id=parts.pop().id,
                component_name=component_name,
            )
        if camera is not None:
            data = await self._get_image_from_camera(camera)
            await self.client.data_client.file_upload(
                part_id=parts.pop().id,
                component_name=component_name,
                file_name=file_name,
                file_extension=".jpeg",
                data=data,
            )

    async def get_classifications(self, call: ServiceCall) -> ServiceResponse:
        """Accept input configuration to request classifications."""
        filepath = call.data.get("filepath")
        camera = call.data.get("camera")
        classifier_name = call.data.get("classifier_name")
        count = int(call.data.get("count", 2))
        confidence_threshold = float(call.data.get("confidence_threshold", 0.6))

        async with await self._get_robot_client(
            call.data.get("robot_secret"), call.data.get("robot_address")
        ) as robot:
            classifier = VisionClient.from_robot(robot, classifier_name)
            image = Image.open(filepath) if filepath is not None else None
            cam_bytes = (
                await self._get_image_from_camera(camera) if camera is not None else b""
            )
            image = RawImage(cam_bytes, "jpeg") if len(cam_bytes) > 0 else None

        if image is None:
            return {
                "classifications": [],
                "img_src": filepath or None,
            }

        img_src = filepath or self._encode_image(image)
        classifications = await classifier.get_classifications(image, count)

        return {
            "classifications": [
                {"name": c.class_name, "confidence": c.confidence}
                for c in classifications
                if c.confidence >= confidence_threshold
            ],
            "img_src": img_src,
        }

    async def get_detections(self, call: ServiceCall) -> ServiceResponse:
        """Accept input configuration to request detections."""
        filepath = call.data.get("filepath")
        camera = call.data.get("camera")
        detector_name = call.data.get("detector_name")
        confidence_threshold = float(call.data.get("confidence_threshold", 0.6))

        async with await self._get_robot_client(
            call.data.get("robot_secret"), call.data.get("robot_address")
        ) as robot:
            detector = VisionClient.from_robot(robot, detector_name)
            image = Image.open(filepath) if filepath is not None else None
            cam_bytes = (
                await self._get_image_from_camera(camera) if camera is not None else b""
            )
            image = RawImage(cam_bytes, "jpeg") if len(cam_bytes) > 0 else None

        if image is None:
            return {
                "detections": [],
                "img_src": filepath or None,
            }

        img_src = filepath or self._encode_image(image)
        detections = await detector.get_detections(image)

        return {
            "detections": [
                {
                    "name": c.class_name,
                    "confidence": c.confidence,
                    "x_min": c.x_min,
                    "y_min": c.y_min,
                    "x_max": c.x_max,
                    "y_max": c.y_max,
                }
                for c in detections
                if c.confidence >= confidence_threshold
            ],
            "img_src": img_src,
        }

    def _encode_image(self, image: RawImage):
        image_string = (
            str(base64.b64encode(image.data))
            .replace("\\n", "")
            .replace("b'", "")
            .replace("'", "")
        )
        return f"data:image/png;base64,{image_string}"

    async def _get_image_from_camera(self, camera_name: str) -> bytes:
        cam_entity = er.async_get(self.hass).async_get(camera_name)
        if cam_entity is None:
            raise ServiceValidationError(
                f"A camera entity called {camera_name} was not found",
                translation_key="camera_entity_not_found",
                translation_placeholders={
                    "camera_name": camera_name,
                },
            )

        cam = self.hass.data[cam_entity.domain].get_entity(camera_name)

        if cam is None:
            raise ServiceValidationError(
                f"A camera for the entity {camera_name} was not found",
                translation_key="camera_not_found",
                translation_placeholders={"camera_name": camera_name},
            )

        return await cam.async_camera_image()

    async def _get_robot_client(
        self, robot_secret: str | None, robot_address: str | None
    ) -> RobotClient:
        """Check initialized data to create robot client."""
        address = self.data.get("address")
        payload = self.data.get("secret")
        if self.data["credential_type"] == "api-key":
            if robot_secret is None or robot_address is None:
                raise ServiceValidationError(
                    "The robot location and secret are required for this connection type.",
                    translation_key="robot_credentials_required",
                )
            address = robot_address
            payload = robot_secret

        if address is None or payload is None:
            raise ServiceValidationError(
                "The necessary credentials for the RobotClient could not be found.",
                translation_key="robot_credentials_not_found",
            )

        credentials = Credentials(type="robot-location-secret", payload=payload)
        robot_options = RobotClient.Options(
            refresh_interval=0, dial_options=DialOptions(credentials=credentials)
        )
        return await RobotClient.at_address(address, robot_options)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up viam from a config entry."""
    credential_type = entry.data["credential_type"]
    payload = entry.data["secret"]
    auth_entity = entry.data["address"]
    if credential_type == "api-key":
        payload = entry.data["api_key"]
        auth_entity = entry.data["api_id"]

    credentials = Credentials(type=credential_type, payload=payload)
    dial_options = DialOptions(auth_entity=auth_entity, credentials=credentials)
    viam_client = await ViamClient.create_from_dial_options(dial_options=dial_options)
    manager = ViamManager(hass, viam_client, entry.entry_id, dict(entry.data))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = manager
    manager.register_services()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
    manager: ViamManager = hass.data[DOMAIN].pop(entry.entry_id)
    manager.unload()

    return True
