"""The viam integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from viam.app.app_client import RobotPart
from viam.app.viam_client import ViamClient
from viam.rpc.dial import Credentials, DialOptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
        self.hass.services.async_register(DOMAIN, "capture_data", self.capture_data)
        self.hass.services.async_register(DOMAIN, "capture_image", self.capture_image)

    def unload(self) -> None:
        """Clean up any open clients."""
        self.hass.services.remove(DOMAIN, "capture_data")
        self.hass.services.remove(DOMAIN, "capture_image")
        self.client.close()

    async def capture_data(self, call: ServiceCall) -> None:
        """Accept input from service call to send to Viam."""
        parts: list[RobotPart] = await self.client.app_client.get_robot_parts(
            robot_id=self.data["robot_id"]
        )
        data = [call.data.get("values")]
        component_type = call.data.get("component_type", "sensor")
        component_name = call.data.get("component_name")
        assert data is not None and component_name is not None

        await self.client.data_client.tabular_data_capture_upload(
            tabular_data=data,
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
            cam_entity = er.async_get(self.hass).async_get(camera)
            assert cam_entity is not None
            cam = self.hass.data[cam_entity.domain].get_entity(camera)
            assert cam is not None
            data = await cam.async_camera_image()
            await self.client.data_client.file_upload(
                part_id=parts.pop().id,
                component_name=component_name,
                file_name=file_name,
                file_extension=".jpeg",
                data=data,
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up viam from a config entry."""
    credential_type = entry.data["credential_type"]
    payload = (
        entry.data["api_key"] if credential_type == "api-key" else entry.data["secret"]
    )
    auth_entity = (
        entry.data["api_id"] if credential_type == "api-key" else entry.data["address"]
    )
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
