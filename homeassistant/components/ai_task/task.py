"""AI tasks to be handled by agents."""

from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path
import tempfile
from typing import Any

import voluptuous as vol

from homeassistant.components import camera, conversation, media_source
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.chat_session import async_get_chat_session

from .const import DATA_COMPONENT, DATA_PREFERENCES, AITaskEntityFeature


def _save_camera_snapshot(image: camera.Image) -> Path:
    """Save camera snapshot to temp file."""
    with tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=mimetypes.guess_extension(image.content_type, False),
        delete=False,
    ) as temp_file:
        temp_file.write(image.content)
        return Path(temp_file.name)


async def async_generate_data(
    hass: HomeAssistant,
    *,
    task_name: str,
    entity_id: str | None = None,
    instructions: str,
    structure: vol.Schema | None = None,
    attachments: list[dict] | None = None,
) -> GenDataTaskResult:
    """Run a task in the AI Task integration."""
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

    # Resolve attachments
    resolved_attachments: list[conversation.Attachment] = []
    created_files: list[Path] = []

    if (
        attachments
        and AITaskEntityFeature.SUPPORT_ATTACHMENTS not in entity.supported_features
    ):
        raise HomeAssistantError(
            f"AI Task entity {entity_id} does not support attachments"
        )

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

    with async_get_chat_session(hass) as session:
        if created_files:

            def cleanup_files() -> None:
                """Cleanup temporary files."""
                for file in created_files:
                    file.unlink(missing_ok=True)

            @callback
            def cleanup_files_callback() -> None:
                """Cleanup temporary files."""
                hass.async_add_executor_job(cleanup_files)

            session.async_on_cleanup(cleanup_files_callback)

        return await entity.internal_async_generate_data(
            session,
            GenDataTask(
                name=task_name,
                instructions=instructions,
                structure=structure,
                attachments=resolved_attachments or None,
            ),
        )


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
