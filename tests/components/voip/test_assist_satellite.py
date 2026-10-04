"""Test the Assist Satellite platform."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.components.voip.assist_satellite import VoipAssistSatellite
from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent as intent_helper


@pytest.mark.parametrize(
    ("intent_args", "message"),
    [
        (
            {},
            "0:02:00 timer finished",
        ),
        (
            {"name": {"value": "pizza"}},
            "pizza finished",
        ),
    ],
)
async def test_timer_events(
    hass: HomeAssistant, voip_device: VoIPDevice, intent_args: dict, message: str
) -> None:
    """Test for timer events."""

    await intent_helper.async_handle(
        hass,
        "test",
        intent_helper.INTENT_START_TIMER,
        {
            "minutes": {"value": 2},
        }
        | intent_args,
        device_id=voip_device.device_id,
    )

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.VoipAssistSatellite._resolve_announcement_media_id",
        ) as mock_resolve,
        patch(
            "homeassistant.components.voip.assist_satellite.VoipAssistSatellite.async_announce",
        ) as mock_announce,
    ):
        await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_DECREASE_TIMER,
            {
                "minutes": {"value": 2},
            },
            device_id=voip_device.device_id,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_resolve.mock_calls) == 1
    assert len(mock_announce.mock_calls) == 1
    assert mock_resolve.mock_calls[0][1][0] == message


async def test_run_start_streams_pipeline_audio(
    hass: HomeAssistant,
    satellite: VoipAssistSatellite,
) -> None:
    """Test RUN_START can immediately stream processor-produced audio."""
    stream = Mock()
    with (
        patch(
            "homeassistant.components.voip.assist_satellite.async_get_audio_output_stream",
            return_value=stream,
        ),
        patch.object(satellite, "_send_tts", new_callable=AsyncMock) as send_tts,
    ):
        satellite.on_pipeline_event(
            PipelineEvent(
                PipelineEventType.RUN_START,
                {
                    "tts_output": {
                        "token": "pipeline-output",
                        "start_streaming": True,
                    }
                },
            )
        )
        await hass.async_block_till_done()

        satellite.on_pipeline_event(
            PipelineEvent(
                PipelineEventType.TTS_END,
                {"tts_output": {"token": "pipeline-output"}},
            )
        )
        await hass.async_block_till_done()

    send_tts.assert_awaited_once_with(tts_stream=stream, wait_for_tone=False)
    assert not satellite._tts_done.is_set()
