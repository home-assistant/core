"""Test the Assist Satellite platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent as intent_helper


@pytest.mark.parametrize(
    ("duration_args", "intent_args", "message"),
    [
        (
            {"minutes": {"value": 2}},
            {},
            "2 minute timer finished",
        ),
        (
            {"hours": {"value": 1}, "seconds": {"value": 30}},
            {},
            "1 hour 30 second timer finished",
        ),
        (
            {"minutes": {"value": 2}},
            {"name": {"value": "pizza"}},
            "pizza finished",
        ),
    ],
)
async def test_timer_events(
    hass: HomeAssistant,
    voip_device: VoIPDevice,
    duration_args: dict,
    intent_args: dict,
    message: str,
) -> None:
    """Test for timer events."""

    await intent_helper.async_handle(
        hass,
        "test",
        intent_helper.INTENT_START_TIMER,
        duration_args | intent_args,
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
            duration_args,
            device_id=voip_device.device_id,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_resolve.mock_calls) == 1
    assert len(mock_announce.mock_calls) == 1
    assert mock_resolve.mock_calls[0][1][0] == message
