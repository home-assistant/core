"""Test the Assist Satellite platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent as intent_helper


@pytest.mark.parametrize(
    ("intent_args", "added_minutes", "message"),
    [
        pytest.param({}, 0, "0:02:00 timer finished", id="unnamed"),
        pytest.param({}, 1, "0:03:00 timer finished", id="unnamed_time_added"),
        pytest.param({"name": {"value": "pizza"}}, 0, "pizza finished", id="named"),
    ],
)
async def test_timer_events(
    hass: HomeAssistant,
    voip_device: VoIPDevice,
    intent_args: dict,
    added_minutes: int,
    message: str,
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
    await intent_helper.async_handle(
        hass,
        "test",
        intent_helper.INTENT_INCREASE_TIMER,
        {"minutes": {"value": added_minutes}},
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
                "minutes": {"value": 2 + added_minutes},
            },
            device_id=voip_device.device_id,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_resolve.mock_calls) == 1
    assert len(mock_announce.mock_calls) == 1
    assert mock_resolve.mock_calls[0][1][0] == message


@pytest.mark.parametrize(
    "intent_type",
    [
        intent_helper.INTENT_PAUSE_TIMER,
        intent_helper.INTENT_CANCEL_TIMER,
    ],
)
async def test_timer_events_not_announced(
    hass: HomeAssistant, voip_device: VoIPDevice, intent_type: str
) -> None:
    """Test only finished timers are announced."""
    with patch(
        "homeassistant.components.voip.assist_satellite.VoipAssistSatellite.async_announce",
    ) as mock_announce:
        await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_START_TIMER,
            {"minutes": {"value": 2}},
            device_id=voip_device.device_id,
        )
        await intent_helper.async_handle(
            hass, "test", intent_type, {}, device_id=voip_device.device_id
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_announce.assert_not_called()
