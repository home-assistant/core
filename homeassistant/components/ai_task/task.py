"""AI tasks to be handled by agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
import mimetypes
from pathlib import Path
import tempfile
from typing import Any

import voluptuous as vol

from homeassistant.components import camera, conversation, media_source
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.chat_session import ChatSession, async_get_chat_session
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.network import get_url
from homeassistant.util import RE_SANITIZE_FILENAME, slugify

from .const import (
    DATA_COMPONENT,
    DATA_IMAGES,
    DATA_PREFERENCES,
    DOMAIN,
    IMAGE_EXPIRY_TIME,
    MAX_IMAGES,
    AITaskEntityFeature,
)


def _save_camera_snapshot(image: camera.Image) -> Path:
    """Save camera snapshot to temp file."""
    with tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=mimetypes.guess_extension(image.content_type, False),
        delete=False,
    ) as temp_file:
        temp_file.write(image.content)
        return Path(temp_file.name)


async def _resolve_attachments(
    hass: HomeAssistant,
    session: ChatSession,
    attachments: list[dict] | None = None,
) -> list[conversation.Attachment]:
    """Resolve attachments for a task."""
    resolved_attachments: list[conversation.Attachment] = []
    created_files: list[Path] = []

    for attachment in attachments or []:
        media_content_id = attachment["media_content_id"]

        # Special case for camera media sources
        if media_content_id.startswith("media-source://camera/"):
            # Extract entity_id from the media content ID
            entity_id = media_content_id.removeprefix("media-source://camera/")

            # Get snapshot from camera
            image = await camera.async_get_image(hass, entity_id)

            temp_filename = await hass.async_add_executor_job(
                _save_camera_snapshot, image
            )
            created_files.append(temp_filename)

            resolved_attachments.append(
                conversation.Attachment(
                    media_content_id=media_content_id,
                    mime_type=image.content_type,
                    path=temp_filename,
                )
            )
        else:
            # Handle regular media sources
            media = await media_source.async_resolve_media(hass, media_content_id, None)
            if media.path is None:
                raise HomeAssistantError(
                    "Only local attachments are currently supported"
                )
            resolved_attachments.append(
                conversation.Attachment(
                    media_content_id=media_content_id,
                    mime_type=media.mime_type,
                    path=media.path,
                )
            )

    if not created_files:
        return resolved_attachments

    def cleanup_files() -> None:
        """Cleanup temporary files."""
        for file in created_files:
            file.unlink(missing_ok=True)

    @callback
    def cleanup_files_callback() -> None:
        """Cleanup temporary files."""
        hass.async_add_executor_job(cleanup_files)

    session.async_on_cleanup(cleanup_files_callback)

    return resolved_attachments


async def async_generate_data(
    hass: HomeAssistant,
    *,
    task_name: str,
    entity_id: str | None = None,
    instructions: str,
    structure: vol.Schema | None = None,
    attachments: list[dict] | None = None,
) -> GenDataTaskResult:
    """Run a data generation task in the AI Task integration."""
    if entity_id is None:
        entity_id = hass.data[DATA_PREFERENCES].gen_data_entity_id

    if entity_id is None:
        raise HomeAssistantError("No entity_id provided and no preferred entity set")

    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None:
        raise HomeAssistantError(f"AI Task entity {entity_id} not found")

    if AITaskEntityFeature.GENERATE_DATA not in entity.supported_features:
        raise HomeAssistantError(
            f"AI Task entity {entity_id} does not support generating data"
        )

    if (
        attachments
        and AITaskEntityFeature.SUPPORT_ATTACHMENTS not in entity.supported_features
    ):
        raise HomeAssistantError(
            f"AI Task entity {entity_id} does not support attachments"
        )

    with async_get_chat_session(hass) as session:
        resolved_attachments = await _resolve_attachments(hass, session, attachments)

        return await entity.internal_async_generate_data(
            session,
            GenDataTask(
                name=task_name,
                instructions=instructions,
                structure=structure,
                attachments=resolved_attachments or None,
            ),
        )


def _cleanup_images(image_storage: dict[str, ImageData], num_to_remove: int) -> None:
    """Remove old images to keep the storage size under the limit."""
    if num_to_remove <= 0:
        return

    if num_to_remove >= len(image_storage):
        image_storage.clear()
        return

    sorted_images = sorted(
        image_storage.items(),
        key=lambda item: item[1].timestamp,
    )

    for filename, _ in sorted_images[:num_to_remove]:
        image_storage.pop(filename, None)


async def async_generate_image(
    hass: HomeAssistant,
    *,
    task_name: str,
    entity_id: str,
    instructions: str,
    attachments: list[dict] | None = None,
) -> ServiceResponse:
    """Run an image generation task in the AI Task integration."""
    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None:
        raise HomeAssistantError(f"AI Task entity {entity_id} not found")

    if AITaskEntityFeature.GENERATE_IMAGE not in entity.supported_features:
        raise HomeAssistantError(
            f"AI Task entity {entity_id} does not support generating images"
        )

    if (
        attachments
        and AITaskEntityFeature.SUPPORT_ATTACHMENTS not in entity.supported_features
    ):
        raise HomeAssistantError(
            f"AI Task entity {entity_id} does not support attachments"
        )

    with async_get_chat_session(hass) as session:
        resolved_attachments = await _resolve_attachments(hass, session, attachments)

        task_result = await entity.internal_async_generate_image(
            session,
            GenImageTask(
                name=task_name,
                instructions=instructions,
                attachments=resolved_attachments or None,
            ),
        )

    service_result = task_result.as_dict()
    image_data = service_result.pop("image_data")
    if service_result.get("revised_prompt") is None:
        service_result["revised_prompt"] = instructions

    image_storage = hass.data[DATA_IMAGES]

    if len(image_storage) + 1 > MAX_IMAGES:
        _cleanup_images(image_storage, len(image_storage) + 1 - MAX_IMAGES)

    current_time = datetime.now()
    ext = mimetypes.guess_extension(task_result.mime_type, False) or ".png"
    sanitized_task_name = RE_SANITIZE_FILENAME.sub("", slugify(task_name))
    filename = f"{current_time.strftime('%Y-%m-%d_%H%M%S')}_{sanitized_task_name}{ext}"

    image_storage[filename] = ImageData(
        data=image_data,
        timestamp=int(current_time.timestamp()),
        mime_type=task_result.mime_type,
        title=service_result["revised_prompt"],
    )

    def _purge_image(filename: str, now: datetime) -> None:
        """Remove image from storage."""
        image_storage.pop(filename, None)

    if IMAGE_EXPIRY_TIME > 0:
        async_call_later(hass, IMAGE_EXPIRY_TIME, partial(_purge_image, filename))

    service_result["url"] = get_url(hass) + async_sign_path(
        hass,
        f"/api/{DOMAIN}/images/{filename}",
        timedelta(seconds=IMAGE_EXPIRY_TIME or 1800),
    )
    service_result["media_source_id"] = f"media-source://{DOMAIN}/images/{filename}"

    return service_result


@dataclass(slots=True)
class GenDataTask:
    """Gen data task to be processed."""

    name: str
    """Name of the task."""

    instructions: str
    """Instructions on what needs to be done."""

    structure: vol.Schema | None = None
    """Optional structure for the data to be generated."""

    attachments: list[conversation.Attachment] | None = None
    """List of attachments to go along the instructions."""

    def __str__(self) -> str:
        """Return task as a string."""
        return f"<GenDataTask {self.name}: {id(self)}>"


@dataclass(slots=True)
class GenDataTaskResult:
    """Result of gen data task."""

    conversation_id: str
    """Unique identifier for the conversation."""

    data: Any
    """Data generated by the task."""

    def as_dict(self) -> dict[str, Any]:
        """Return result as a dict."""
        return {
            "conversation_id": self.conversation_id,
            "data": self.data,
        }


@dataclass(slots=True)
class GenImageTask:
    """Gen image task to be processed."""

    name: str
    """Name of the task."""

    instructions: str
    """Instructions on what needs to be done."""

    attachments: list[conversation.Attachment] | None = None
    """List of attachments to go along the instructions."""

    def __str__(self) -> str:
        """Return task as a string."""
        return f"<GenImageTask {self.name}: {id(self)}>"


@dataclass(slots=True)
class GenImageTaskResult:
    """Result of gen image task."""

    image_data: bytes
    """Raw image data generated by the model."""

    conversation_id: str
    """Unique identifier for the conversation."""

    mime_type: str
    """MIME type of the generated image."""

    width: int | None = None
    """Width of the generated image, if available."""

    height: int | None = None
    """Height of the generated image, if available."""

    model: str | None = None
    """Model used to generate the image, if available."""

    revised_prompt: str | None = None
    """Revised prompt used to generate the image, if applicable."""

    def as_dict(self) -> dict[str, Any]:
        """Return result as a dict."""
        return {
            "image_data": self.image_data,
            "conversation_id": self.conversation_id,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "model": self.model,
            "revised_prompt": self.revised_prompt,
        }


@dataclass(slots=True)
class ImageData:
    """Image data for stored generated images."""

    data: bytes
    """Raw image data."""

    timestamp: int
    """Timestamp when the image was generated, as a Unix timestamp."""

    mime_type: str
    """MIME type of the image."""

    title: str
    """Title of the image, usually the prompt used to generate it."""

    def __str__(self) -> str:
        """Return image data as a string."""
        return f"<ImageData {self.title}: {id(self)}>"
