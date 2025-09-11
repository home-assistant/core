"""Test tasks for the AI Task integration."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import media_source
from homeassistant.components.ai_task import (
    AITaskEntityFeature,
    ImageData,
    async_generate_data,
    async_generate_image,
)
from homeassistant.components.camera import Image
from homeassistant.components.conversation import async_get_chat_log
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, llm
from homeassistant.util import dt as dt_util

from .conftest import TEST_ENTITY_ID, MockAITaskEntity

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator


async def test_generate_data_preferred_entity(
    hass: HomeAssistant,
    init_components: None,
    mock_ai_task_entity: MockAITaskEntity,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test generating data with entity via preferences."""
    client = await hass_ws_client(hass)

    with pytest.raises(
        HomeAssistantError, match="No entity_id provided and no preferred entity set"
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            instructions="Test prompt",
        )

    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_data_entity_id": "ai_task.unknown",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    with pytest.raises(
        HomeAssistantError, match="AI Task entity ai_task.unknown not found"
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            instructions="Test prompt",
        )

    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_data_entity_id": TEST_ENTITY_ID,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    llm_api = llm.AssistAPI(hass)
    result = await async_generate_data(
        hass,
        task_name="Test Task",
        instructions="Test prompt",
        llm_api=llm_api,
    )
    assert result.data == "Mock result"
    as_dict = result.as_dict()
    assert as_dict["conversation_id"] == result.conversation_id
    assert as_dict["data"] == "Mock result"
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN

    with (
        chat_session.async_get_chat_session(hass, result.conversation_id) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        assert chat_log.llm_api.api is llm_api

    mock_ai_task_entity.supported_features = AITaskEntityFeature(0)
    with pytest.raises(
        HomeAssistantError,
        match="AI Task entity ai_task.test_task_entity does not support generating data",
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            instructions="Test prompt",
        )


async def test_generate_data_unknown_entity(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test generating data with an unknown entity."""

    with pytest.raises(
        HomeAssistantError, match="AI Task entity ai_task.unknown_entity not found"
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.unknown_entity",
            instructions="Test prompt",
        )


@freeze_time("2025-06-14 22:59:00")
async def test_run_data_task_updates_chat_log(
    hass: HomeAssistant,
    init_components: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that generating data updates the chat log."""
    result = await async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=TEST_ENTITY_ID,
        instructions="Test prompt",
    )
    assert result.data == "Mock result"

    with (
        chat_session.async_get_chat_session(hass, result.conversation_id) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        assert chat_log.content == snapshot


async def test_generate_data_attachments_not_supported(
    hass: HomeAssistant,
    init_components: None,
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test generating data with attachments when entity doesn't support them."""
    # Remove attachment support from the entity
    mock_ai_task_entity._attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    with pytest.raises(
        HomeAssistantError,
        match="AI Task entity ai_task.test_task_entity does not support attachments",
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=TEST_ENTITY_ID,
            instructions="Test prompt",
            attachments=[
                {
                    "media_content_id": "media-source://mock/test.mp4",
                    "media_content_type": "video/mp4",
                }
            ],
        )


async def test_generate_data_mixed_attachments(
    hass: HomeAssistant,
    init_components: None,
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test generating data with both camera and regular media source attachments."""
    with (
        patch(
            "homeassistant.components.camera.async_get_image",
            return_value=Image(content_type="image/jpeg", content=b"fake_camera_jpeg"),
        ) as mock_get_image,
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="http://example.com/test.mp4",
                mime_type="video/mp4",
                path=Path("/media/test.mp4"),
            ),
        ) as mock_resolve_media,
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=TEST_ENTITY_ID,
            instructions="Analyze these files",
            attachments=[
                {
                    "media_content_id": "media-source://camera/camera.front_door",
                    "media_content_type": "image/jpeg",
                },
                {
                    "media_content_id": "media-source://media_player/video.mp4",
                    "media_content_type": "video/mp4",
                },
            ],
        )

    # Verify both methods were called
    mock_get_image.assert_called_once_with(hass, "camera.front_door")
    mock_resolve_media.assert_called_once_with(
        hass, "media-source://media_player/video.mp4", None
    )

    # Check attachments
    assert len(mock_ai_task_entity.mock_generate_data_tasks) == 1
    task = mock_ai_task_entity.mock_generate_data_tasks[0]
    assert task.attachments is not None
    assert len(task.attachments) == 2

    # Check camera attachment
    camera_attachment = task.attachments[0]
    assert (
        camera_attachment.media_content_id == "media-source://camera/camera.front_door"
    )
    assert camera_attachment.mime_type == "image/jpeg"
    assert isinstance(camera_attachment.path, Path)
    assert camera_attachment.path.suffix == ".jpg"

    # Verify camera snapshot content
    assert camera_attachment.path.exists()
    content = await hass.async_add_executor_job(camera_attachment.path.read_bytes)
    assert content == b"fake_camera_jpeg"

    # Trigger clean up
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT + timedelta(seconds=1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify the temporary file cleaned up
    assert not camera_attachment.path.exists()

    # Check regular media attachment
    media_attachment = task.attachments[1]
    assert media_attachment.media_content_id == "media-source://media_player/video.mp4"
    assert media_attachment.mime_type == "video/mp4"
    assert media_attachment.path == Path("/media/test.mp4")


async def test_generate_image(
    hass: HomeAssistant,
    init_components: None,
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test generating image service."""
    with pytest.raises(
        HomeAssistantError, match="AI Task entity ai_task.unknown not found"
    ):
        await async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.unknown",
            instructions="Test prompt",
        )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    result = await async_generate_image(
        hass,
        task_name="Test Task",
        entity_id=TEST_ENTITY_ID,
        instructions="Test prompt",
    )
    assert "image_data" not in result
    assert result["media_source_id"].startswith("media-source://ai_task/images/")
    assert result["media_source_id"].endswith("_test_task.png")
    assert result["url"].startswith("http://10.10.10.10:8123/api/ai_task/images/")
    assert result["url"].count("_test_task.png?authSig=") == 1
    assert result["mime_type"] == "image/png"
    assert result["model"] == "mock_model"
    assert result["revised_prompt"] == "mock_revised_prompt"
    assert result["height"] == 1024
    assert result["width"] == 1536

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN

    mock_ai_task_entity.supported_features = AITaskEntityFeature(0)
    with pytest.raises(
        HomeAssistantError,
        match="AI Task entity ai_task.test_task_entity does not support generating images",
    ):
        await async_generate_image(
            hass,
            task_name="Test Task",
            entity_id=TEST_ENTITY_ID,
            instructions="Test prompt",
        )


async def test_image_cleanup(
    hass: HomeAssistant,
    init_components: None,
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test image cache cleanup."""
    image_storage = hass.data.setdefault("ai_task_images", {})
    image_storage.clear()
    image_storage.update(
        {
            str(idx): ImageData(
                data=b"mock_image_data",
                timestamp=int(datetime.now().timestamp()),
                mime_type="image/png",
                title="Test Image",
            )
            for idx in range(20)
        }
    )
    assert len(image_storage) == 20

    result = await async_generate_image(
        hass,
        task_name="Test Task",
        entity_id=TEST_ENTITY_ID,
        instructions="Test prompt",
    )

    assert result["url"].split("?authSig=")[0].split("/")[-1] in image_storage
    assert len(image_storage) == 20

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
    await hass.async_block_till_done()

    assert len(image_storage) == 19
