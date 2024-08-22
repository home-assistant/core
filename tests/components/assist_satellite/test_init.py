"""Tests for Assist satellite."""

from unittest.mock import patch

from homeassistant.components import assist_pipeline, assist_satellite
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import MockSatelliteEntity


async def test_wait_wake(
    hass: HomeAssistant, mock_satellite: MockSatelliteEntity
) -> None:
    """Test wait_wake service."""
    test_wake_word = "test-wake-word"

    with patch.object(
        mock_satellite,
        "async_trigger_pipeline_on_satellite",
        return_value=assist_satellite.PipelineRunResult(
            detected_wake_word=test_wake_word
        ),
    ) as mock_async_trigger_pipeline_on_satellite:
        result = await hass.services.async_call(
            assist_satellite.DOMAIN,
            assist_satellite.SERVICE_WAIT_WAKE,
            {
                ATTR_ENTITY_ID: mock_satellite.entity_id,
                assist_satellite.ATTR_WAKE_WORDS: [test_wake_word],
            },
            return_response=True,
            blocking=True,
        )

        mock_async_trigger_pipeline_on_satellite.assert_called_once_with(
            assist_pipeline.PipelineStage.WAKE_WORD,
            assist_pipeline.PipelineStage.WAKE_WORD,
            assist_satellite.PipelineRunConfig(wake_word_names=[test_wake_word]),
        )
        assert result == {mock_satellite.entity_id: test_wake_word}


async def test_announce_wait_wake(
    hass: HomeAssistant, mock_satellite: MockSatelliteEntity
) -> None:
    """Test wait_wake service with announcement."""
    test_wake_word = "test-wake-word"
    announce_text = "test-announce-text"

    with patch.object(
        mock_satellite,
        "async_trigger_pipeline_on_satellite",
        return_value=assist_satellite.PipelineRunResult(
            detected_wake_word=test_wake_word
        ),
    ) as mock_async_trigger_pipeline_on_satellite:
        result = await hass.services.async_call(
            assist_satellite.DOMAIN,
            assist_satellite.SERVICE_WAIT_WAKE,
            {
                ATTR_ENTITY_ID: mock_satellite.entity_id,
                assist_satellite.ATTR_ANNOUNCE_TEXT: announce_text,
                assist_satellite.ATTR_WAKE_WORDS: [test_wake_word],
            },
            return_response=True,
            blocking=True,
        )

        assert mock_async_trigger_pipeline_on_satellite.call_count == 2
        assert mock_async_trigger_pipeline_on_satellite.call_args_list[0].args == (
            assist_pipeline.PipelineStage.TTS,
            assist_pipeline.PipelineStage.TTS,
            assist_satellite.PipelineRunConfig(announce_text=announce_text),
        )
        assert mock_async_trigger_pipeline_on_satellite.call_args_list[1].args == (
            assist_pipeline.PipelineStage.WAKE_WORD,
            assist_pipeline.PipelineStage.WAKE_WORD,
            assist_satellite.PipelineRunConfig(wake_word_names=[test_wake_word]),
        )
        assert result == {mock_satellite.entity_id: test_wake_word}


async def test_get_command(
    hass: HomeAssistant, mock_satellite: MockSatelliteEntity
) -> None:
    """Test get_command service."""
    test_command = "test-command"

    with patch.object(
        mock_satellite,
        "async_trigger_pipeline_on_satellite",
        return_value=assist_satellite.PipelineRunResult(command_text=test_command),
    ) as mock_async_trigger_pipeline_on_satellite:
        result = await hass.services.async_call(
            assist_satellite.DOMAIN,
            assist_satellite.SERVICE_GET_COMMAND,
            {ATTR_ENTITY_ID: mock_satellite.entity_id},
            return_response=True,
            blocking=True,
        )

        mock_async_trigger_pipeline_on_satellite.assert_called_once_with(
            assist_pipeline.PipelineStage.STT,
            assist_pipeline.PipelineStage.STT,
            assist_satellite.PipelineRunConfig(),
        )
        assert result == {mock_satellite.entity_id: test_command}


async def test_announce_get_command(
    hass: HomeAssistant, mock_satellite: MockSatelliteEntity
) -> None:
    """Test get_command service with announcement."""
    test_command = "test-command"
    announce_text = "test-announce-text"

    with patch.object(
        mock_satellite,
        "async_trigger_pipeline_on_satellite",
        return_value=assist_satellite.PipelineRunResult(command_text=test_command),
    ) as mock_async_trigger_pipeline_on_satellite:
        result = await hass.services.async_call(
            assist_satellite.DOMAIN,
            assist_satellite.SERVICE_GET_COMMAND,
            {
                ATTR_ENTITY_ID: mock_satellite.entity_id,
                assist_satellite.ATTR_ANNOUNCE_TEXT: announce_text,
            },
            return_response=True,
            blocking=True,
        )

        assert mock_async_trigger_pipeline_on_satellite.call_count == 2
        assert mock_async_trigger_pipeline_on_satellite.call_args_list[0].args == (
            assist_pipeline.PipelineStage.TTS,
            assist_pipeline.PipelineStage.TTS,
            assist_satellite.PipelineRunConfig(announce_text=announce_text),
        )
        assert mock_async_trigger_pipeline_on_satellite.call_args_list[1].args == (
            assist_pipeline.PipelineStage.STT,
            assist_pipeline.PipelineStage.STT,
            assist_satellite.PipelineRunConfig(),
        )
        assert result == {mock_satellite.entity_id: test_command}


async def test_get_command_process(
    hass: HomeAssistant, mock_satellite: MockSatelliteEntity
) -> None:
    """Test get_command service with processing enabled."""
    test_command = "test-command"

    with patch.object(
        mock_satellite,
        "async_trigger_pipeline_on_satellite",
        return_value=assist_satellite.PipelineRunResult(command_text=test_command),
    ) as mock_async_trigger_pipeline_on_satellite:
        result = await hass.services.async_call(
            assist_satellite.DOMAIN,
            assist_satellite.SERVICE_GET_COMMAND,
            {
                ATTR_ENTITY_ID: mock_satellite.entity_id,
                assist_satellite.ATTR_PROCESS: True,
            },
            return_response=True,
            blocking=True,
        )

        # Pipeline should run to TTS stage now
        mock_async_trigger_pipeline_on_satellite.assert_called_once_with(
            assist_pipeline.PipelineStage.STT,
            assist_pipeline.PipelineStage.TTS,
            assist_satellite.PipelineRunConfig(),
        )
        assert result == {mock_satellite.entity_id: test_command}


async def test_say_text(
    hass: HomeAssistant, mock_satellite: MockSatelliteEntity
) -> None:
    """Test say_text service."""
    announce_text = "test-announce-text"

    with patch.object(
        mock_satellite, "async_trigger_pipeline_on_satellite", return_value=None
    ) as mock_async_trigger_pipeline_on_satellite:
        result = await hass.services.async_call(
            assist_satellite.DOMAIN,
            assist_satellite.SERVICE_SAY_TEXT,
            {
                ATTR_ENTITY_ID: mock_satellite.entity_id,
                assist_satellite.ATTR_ANNOUNCE_TEXT: announce_text,
            },
            return_response=False,
            blocking=True,
        )

        mock_async_trigger_pipeline_on_satellite.assert_called_once_with(
            assist_pipeline.PipelineStage.TTS,
            assist_pipeline.PipelineStage.TTS,
            assist_satellite.PipelineRunConfig(announce_text=announce_text),
        )
        assert result is None
