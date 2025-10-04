"""Message sending functionality for the Matrix component."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging
import mimetypes
import os

import aiofiles.os
from nio import AsyncClient
from nio.responses import ErrorResponse, Response, UploadError, UploadResponse
from PIL import Image

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
from homeassistant.core import HomeAssistant

from .const import ATTR_FORMAT, ATTR_IMAGES, FORMAT_HTML
from .types import RoomAnyID, RoomID

_LOGGER = logging.getLogger(__name__)


class MatrixMessages:
    """Handle Matrix message sending."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncClient,
        listening_rooms: dict[RoomAnyID, RoomID],
    ) -> None:
        """Initialize message handler."""
        self.hass = hass
        self._client = client
        self._listening_rooms = listening_rooms

    async def handle_room_send(
        self, target_room: RoomAnyID, message_type: str, content: dict
    ) -> None:
        """Wrap _client.room_send and handle ErrorResponses."""
        response: Response = await self._client.room_send(
            room_id=self._listening_rooms.get(target_room, target_room),
            message_type=message_type,
            content=content,
        )
        if isinstance(response, ErrorResponse):
            _LOGGER.error(
                "Unable to deliver message to room '%s': %s",
                target_room,
                response,
            )
        else:
            _LOGGER.debug("Message delivered to room '%s'", target_room)

    async def handle_multi_room_send(
        self, target_rooms: Sequence[RoomAnyID], message_type: str, content: dict
    ) -> None:
        """Wrap _handle_room_send for multiple target_rooms."""
        await asyncio.wait(
            self.hass.async_create_task(
                self.handle_room_send(
                    target_room=target_room,
                    message_type=message_type,
                    content=content,
                ),
                eager_start=False,
            )
            for target_room in target_rooms
        )

    async def send_image(
        self, image_path: str, target_rooms: Sequence[RoomAnyID]
    ) -> None:
        """Upload an image, then send it to all target_rooms."""
        _is_allowed_path = await self.hass.async_add_executor_job(
            self.hass.config.is_allowed_path, image_path
        )
        if not _is_allowed_path:
            _LOGGER.error("Path not allowed: %s", image_path)
            return

        # Get required image metadata.
        image = await self.hass.async_add_executor_job(Image.open, image_path)
        (width, height) = image.size
        mime_type = mimetypes.guess_type(image_path)[0]
        file_stat = await aiofiles.os.stat(image_path)

        _LOGGER.debug("Uploading file from path, %s", image_path)
        async with aiofiles.open(image_path, "rb") as image_file:
            response, _ = await self._client.upload(
                image_file,
                content_type=mime_type,
                filename=os.path.basename(image_path),
                filesize=file_stat.st_size,
            )
        if isinstance(response, UploadError):
            _LOGGER.error("Unable to upload image to the homeserver: %s", response)
            return
        if isinstance(response, UploadResponse):
            _LOGGER.debug("Successfully uploaded image to the homeserver")
        else:
            _LOGGER.error(
                "Unknown response received when uploading image to homeserver: %s",
                response,
            )
            return

        content = {
            "body": os.path.basename(image_path),
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
                "w": width,
                "h": height,
            },
            "msgtype": "m.image",
            "url": response.content_uri,
        }

        await self.handle_multi_room_send(
            target_rooms=target_rooms, message_type="m.room.message", content=content
        )

    async def send_message(
        self, message: str, target_rooms: list[RoomAnyID], data: dict | None
    ) -> None:
        """Send a message to the Matrix server."""
        content = {"msgtype": "m.text", "body": message}
        if data is not None and data.get(ATTR_FORMAT) == FORMAT_HTML:
            content |= {"format": "org.matrix.custom.html", "formatted_body": message}

        await self.handle_multi_room_send(
            target_rooms=target_rooms, message_type="m.room.message", content=content
        )

        if (
            data is not None
            and (image_paths := data.get(ATTR_IMAGES, []))
            and len(target_rooms) > 0
        ):
            image_tasks = [
                self.hass.async_create_task(
                    self.send_image(image_path, target_rooms), eager_start=False
                )
                for image_path in image_paths
            ]
            await asyncio.wait(image_tasks)

    async def handle_send_message(self, service_data: dict) -> None:
        """Handle the send_message service."""
        await self.send_message(
            service_data[ATTR_MESSAGE],
            service_data[ATTR_TARGET],
            service_data.get(ATTR_DATA),
        )
