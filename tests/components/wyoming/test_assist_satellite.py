"""Test Wyoming assist satellite entity."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from wyoming.info import Attribution, Info as WyomingInfo, Satellite as SatelliteInfo

from homeassistant.components import assist_pipeline, assist_satellite
from homeassistant.components.assist_pipeline import PipelineEvent
from homeassistant.components.wyoming.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .test_satellite import SatelliteAsyncTcpClient, setup_config_entry


async def _get_satellite_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, config_entry_id: str
) -> str:
    """Get the entity ID for the satellite."""
    device = hass.data[DOMAIN][config_entry_id].device
    assert device is not None

    satellite_entity_id = "assist_satellite.test_satellite"
    await hass.async_block_till_done()
    assert hass.states.get(satellite_entity_id) is not None
    return satellite_entity_id


async def test_state_updates(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the satellite correctly updates the assist_in_progress sensor."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})
    assert await async_setup_component(hass, "binary_sensor", {})

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=WyomingInfo(
                satellite=SatelliteInfo(
                    name="Test Satellite",
                    area="Test Area",
                    attribution=Attribution(
                        name="Test Attribution", url="http://test.com"
                    ),
                    installed=True,
                    description="Test Description",
                    version="1.0.0",
                )
            ),
        ),
        patch(
            "homeassistant.components.wyoming.assist_satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient([]),
        ) as mock_client,
    ):
        # The setup_config_entry helper already calls async_setup and async_block_till_done.
        entry = await setup_config_entry(hass)
        await hass.async_block_till_done()

        # Wait for satellite to connect
        await mock_client.connect_event.wait()

        satellite_entity_id = await _get_satellite_entity_id(
            hass, entity_registry, entry.entry_id
        )
        satellite_entity = hass.data["assist_satellite"].get_entity(satellite_entity_id)
        assert satellite_entity is not None

        device = hass.data[DOMAIN][entry.entry_id].device
        assert not device.is_active

        # --- Test STT_START ---
        satellite_entity.on_pipeline_event(
            PipelineEvent(assist_pipeline.PipelineEventType.STT_START)
        )
        await hass.async_block_till_done()
        assert device.is_active

        # --- Test RUN_END ---
        satellite_entity.on_pipeline_event(
            PipelineEvent(assist_pipeline.PipelineEventType.RUN_END)
        )
        await hass.async_block_till_done()
        assert not device.is_active


async def test_announce_and_start_conversation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the announce and start_conversation service calls."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    fake_announcement = assist_satellite.AssistSatelliteAnnouncement(
        message="test",
        media_id="test_media_id",
        original_media_id="",
        tts_token=None,
        media_id_source="url",
    )

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=WyomingInfo(
                satellite=SatelliteInfo(
                    name="Test Satellite",
                    area="Test Area",
                    attribution=Attribution(
                        name="Test Attribution", url="http://test.com"
                    ),
                    installed=True,
                    description="Test Description",
                    version="1.0.0",
                )
            ),
        ),
        patch(
            "homeassistant.components.wyoming.assist_satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient([]),
        ) as mock_client,
        patch(
            "homeassistant.components.wyoming.assist_satellite.WyomingAssistSatellite._resolve_announcement_media_id",
            return_value=fake_announcement,
        ),
        patch(
            "homeassistant.components.wyoming.assist_satellite.WyomingAssistSatellite._play_media"
        ) as mock_play_media,
        patch(
            "homeassistant.components.assist_satellite.entity.async_get_pipeline",
            return_value=assist_pipeline.Pipeline(
                name="test_pipeline",
                language="en",
                conversation_engine="test_engine",
                conversation_language="en",
                stt_engine="test_stt",
                stt_language="en",
                tts_engine="test_tts",
                tts_language="en",
                tts_voice=None,
                wake_word_entity=None,
                wake_word_id=None,
            ),
        ),
    ):
        # The setup_config_entry helper already calls async_setup and async_block_till_done.
        entry = await setup_config_entry(hass)

        satellite_entity_id = await _get_satellite_entity_id(
            hass, entity_registry, entry.entry_id
        )

        # Test announce
        await hass.services.async_call(
            assist_satellite.DOMAIN,
            "announce",
            {"entity_id": satellite_entity_id, "message": "test"},
            blocking=True,
        )
        mock_play_media.assert_called_once_with("test_media_id")
        mock_play_media.reset_mock()

        # Test start_conversation
        await hass.services.async_call(
            assist_satellite.DOMAIN,
            "start_conversation",
            {"entity_id": satellite_entity_id, "start_message": "test"},
            blocking=True,
        )
        mock_play_media.assert_called_with("test_media_id")
        async with asyncio.timeout(1):
            await mock_client.detection_event.wait()
        assert mock_client.detection.name == "command_start"
