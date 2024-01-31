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

from homeassistant.components import camera
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_API_KEY
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_ID,
    CONF_CREDENTIAL_TYPE,
    CONF_ROBOT_ID,
    CONF_SECRET,
    CRED_TYPE_API_KEY,
    CRED_TYPE_LOCATION_SECRET,
    DOMAIN,
    SERVICE_CAMERA,
    SERVICE_CLASSIFIER_NAME,
    SERVICE_COMPONENT_NAME,
    SERVICE_COMPONENT_TYPE,
    SERVICE_CONFIDENCE,
    SERVICE_COUNT,
    SERVICE_DETECTOR_NAME,
    SERVICE_FILE_NAME,
    SERVICE_FILEPATH,
    SERVICE_ROBOT_ADDRESS,
    SERVICE_ROBOT_SECRET,
    SERVICE_VALUES,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({})},
    extra=vol.ALLOW_EXTRA,
)

DATA_CAPTURE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_VALUES): vol.All(dict),
        vol.Required(SERVICE_COMPONENT_NAME): vol.All(str),
        vol.Required(SERVICE_COMPONENT_TYPE, default="sensor"): vol.All(str),
    }
)

IMAGE_SERVICE_FIELDS = {
    vol.Optional(SERVICE_FILEPATH): vol.All(str, vol.IsFile),
    vol.Optional(SERVICE_CAMERA): vol.All(str),
}
VISION_SERVICE_FIELDS = {
    vol.Optional(SERVICE_CONFIDENCE, default="0.6"): vol.All(
        str, vol.Coerce(float), vol.Range(min=0, max=1)
    ),
    vol.Optional(SERVICE_ROBOT_ADDRESS): vol.All(str),
    vol.Optional(SERVICE_ROBOT_SECRET): vol.All(str),
}

CAPTURE_IMAGE_SERVICE_SCHEMA = vol.Schema(
    {
        **IMAGE_SERVICE_FIELDS,
        vol.Optional(SERVICE_FILE_NAME, default="camera"): vol.All(str),
        vol.Optional(SERVICE_COMPONENT_NAME): vol.All(str),
    }
)

CLASSIFICATION_SERVICE_SCHEMA = vol.Schema(
    {
        **IMAGE_SERVICE_FIELDS,
        **VISION_SERVICE_FIELDS,
        vol.Required(SERVICE_CLASSIFIER_NAME): vol.All(str),
        vol.Optional(SERVICE_COUNT, default="2"): vol.All(str, vol.Coerce(int)),
    }
)

DETECTIONS_SERVICE_SCHEMA = vol.Schema(
    {
        **IMAGE_SERVICE_FIELDS,
        **VISION_SERVICE_FIELDS,
        vol.Required(SERVICE_DETECTOR_NAME): vol.All(str),
    }
)


def _fetch_image(filepath: str | None):
    if filepath is None:
        return None
    return Image.open(filepath)


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
        self.client.close()

    async def capture_data(self, call: ServiceCall) -> None:
        """Accept input from service call to send to Viam."""
        parts: list[RobotPart] = await self.client.app_client.get_robot_parts(
            robot_id=self.data[CONF_ROBOT_ID]
        )
        values = [call.data.get(SERVICE_VALUES)]
        component_type = call.data.get(SERVICE_COMPONENT_TYPE, "sensor")
        component_name = call.data.get(SERVICE_COMPONENT_NAME)

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
            robot_id=self.data[CONF_ROBOT_ID]
        )
        filepath = call.data.get(SERVICE_FILEPATH)
        camera_entity = call.data.get(SERVICE_CAMERA)
        component_name = call.data.get(SERVICE_COMPONENT_NAME)
        file_name = call.data.get(SERVICE_FILE_NAME, "camera")

        if filepath is not None:
            await self.client.data_client.file_upload_from_path(
                filepath=filepath,
                part_id=parts.pop().id,
                component_name=component_name,
            )
        if camera_entity is not None:
            image = await camera.async_get_image(self.hass, camera_entity)
            await self.client.data_client.file_upload(
                part_id=parts.pop().id,
                component_name=component_name,
                file_name=file_name,
                file_extension=".jpeg",
                data=image.content,
            )

    async def get_classifications(self, call: ServiceCall) -> ServiceResponse:
        """Accept input configuration to request classifications."""
        filepath = call.data.get(SERVICE_FILEPATH)
        camera_entity = call.data.get(SERVICE_CAMERA)
        classifier_name = call.data.get(SERVICE_CLASSIFIER_NAME)
        count = int(call.data.get(SERVICE_COUNT, 2))
        confidence_threshold = float(call.data.get(SERVICE_CONFIDENCE, 0.6))

        async with await self._get_robot_client(
            call.data.get(SERVICE_ROBOT_SECRET), call.data.get(SERVICE_ROBOT_ADDRESS)
        ) as robot:
            classifier = VisionClient.from_robot(robot, classifier_name)
            image = await self._get_image(filepath, camera_entity)

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
        filepath = call.data.get(SERVICE_FILEPATH)
        camera_entity = call.data.get(SERVICE_CAMERA)
        detector_name = call.data.get(SERVICE_DETECTOR_NAME)
        confidence_threshold = float(call.data.get(SERVICE_CONFIDENCE, 0.6))

        async with await self._get_robot_client(
            call.data.get(SERVICE_ROBOT_SECRET), call.data.get(SERVICE_ROBOT_ADDRESS)
        ) as robot:
            detector = VisionClient.from_robot(robot, detector_name)
            image = await self._get_image(filepath, camera_entity)

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

    def _encode_image(self, image: Image.Image | RawImage):
        image_bytes = b""
        if isinstance(image, Image.Image):
            image_bytes = image.tobytes()
        if isinstance(image, RawImage):
            image_bytes = image.data

        image_string = base64.b64encode(image_bytes).decode()
        return f"data:image/jpeg;base64,{image_string}"

    async def _get_image(self, filepath: str | None, camera_entity: str | None):
        if filepath is not None:
            return await self.hass.async_add_executor_job(_fetch_image, filepath)
        if camera_entity is not None:
            image = await camera.async_get_image(self.hass, camera_entity)
            return RawImage(image.content, image.content_type)

        return None

    async def _get_robot_client(
        self, robot_secret: str | None, robot_address: str | None
    ) -> RobotClient:
        """Check initialized data to create robot client."""
        address = self.data.get(CONF_ADDRESS)
        payload = self.data.get(CONF_SECRET)
        if self.data[CONF_CREDENTIAL_TYPE] == CRED_TYPE_API_KEY:
            if robot_secret is None or robot_address is None:
                raise ServiceValidationError(
                    "The robot location and secret are required for this connection type.",
                    translation_domain=DOMAIN,
                    translation_key="robot_credentials_required",
                )
            address = robot_address
            payload = robot_secret

        if address is None or payload is None:
            raise ServiceValidationError(
                "The necessary credentials for the RobotClient could not be found.",
                translation_domain=DOMAIN,
                translation_key="robot_credentials_not_found",
            )

        credentials = Credentials(type=CRED_TYPE_LOCATION_SECRET, payload=payload)
        robot_options = RobotClient.Options(
            refresh_interval=0, dial_options=DialOptions(credentials=credentials)
        )
        return await RobotClient.at_address(address, robot_options)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Viam component."""
    config_entries = hass.config_entries.async_entries(DOMAIN)
    if not config_entries:
        raise HomeAssistantError(
            "No Viam config entries found",
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
        )

    for config_entry in config_entries:
        if config_entry.state != ConfigEntryState.LOADED:
            raise HomeAssistantError(
                f"{config_entry.title} is not loaded",
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={
                    "config_entry_title": config_entry.title,
                },
            )
        manager: ViamManager = hass.data[DOMAIN][config_entry.entry_id]
        manager.register_services()
        break

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up viam from a config entry."""
    credential_type = entry.data[CONF_CREDENTIAL_TYPE]
    payload = entry.data[CONF_SECRET]
    auth_entity = entry.data[CONF_ADDRESS]
    if credential_type == CRED_TYPE_API_KEY:
        payload = entry.data[CONF_API_KEY]
        auth_entity = entry.data[CONF_API_ID]

    credentials = Credentials(type=credential_type, payload=payload)
    dial_options = DialOptions(auth_entity=auth_entity, credentials=credentials)
    viam_client = await ViamClient.create_from_dial_options(dial_options=dial_options)
    manager = ViamManager(hass, viam_client, entry.entry_id, dict(entry.data))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = manager

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    manager: ViamManager = hass.data[DOMAIN].pop(entry.entry_id)
    manager.unload()

    return True
