"""Test Wyoming assist satellite entity."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from homeassistant.components import assist_pipeline, assist_satellite
from homeassistant.components.assist_pipeline import PipelineEvent
from homeassistant.components.wyoming.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import SATELLITE_INFO
from .test_satellite import SatelliteAsyncTcpClient, setup_config_entry


async def _get_satellite_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, config_entry_id: str
) -> str:
    """Get the entity ID for the satellite."""
    device = hass.data[DOMAIN][config_entry_id].device
    assert device is not None

    satellite_entry = entity_registry.async_get_entity_id(
        assist_satellite.DOMAIN, DOMAIN, device.satellite_id
    )
    assert satellite_entry is not None
    return satellite_entry


async def test_state_updates(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the satellite correctly updates the assist_in_progress sensor."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.assist_satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient([]),
        ),
        patch(
            "homeassistant.components.wyoming.assist_satellite.WyomingAssistSatellite.run"
        ),
    ):
        # The setup_config_entry helper already calls async_setup and async_block_till_done.
        entry = await setup_config_entry(hass)

        satellite_entity_id = await _get_satellite_entity_id(
            hass, entity_registry, entry.entry_id
        )
        satellite_entity = hass.data["assist_satellite"].get_entity(satellite_entity_id)
        assert satellite_entity is not None

        assist_sensor_id = "binary_sensor.test_satellite_assist_in_progress"
        assert hass.states.get(assist_sensor_id) is not None
        assert hass.states.get(assist_sensor_id).state != "on"

        # --- Test STT_START ---
        satellite_entity.on_pipeline_event(
            PipelineEvent(assist_pipeline.PipelineEventType.STT_START)
        )
        await hass.async_block_till_done()
        assert hass.states.get(assist_sensor_id).state == "on"

        # --- Test RUN_END ---
        satellite_entity.on_pipeline_event(
            PipelineEvent(assist_pipeline.PipelineEventType.RUN_END)
        )
        await hass.async_block_till_done()
        assert hass.states.get(assist_sensor_id).state != "on"


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
            return_value=SATELLITE_INFO,
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
