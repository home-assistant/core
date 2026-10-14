"""Tests for the SUPLA switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.supla import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed

ENTITY_ID = "switch.living_room_light"
CHANNELS = [
    {
        "id": 1,
        "caption": "Living room light",
        "channelNumber": 0,
        "function": {"name": "LIGHTSWITCH"},
        "iodevice": {"gUIDString": "ABCDEF"},
        "state": {"connected": True, "on": True},
    }
]


async def test_unavailable_on_update_failure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the switch is unavailable while the coordinator update fails."""
    with patch("homeassistant.components.supla.SuplaAPI") as mock_api_class:
        api = mock_api_class.return_value
        api.get_server_info = AsyncMock(return_value={"authenticated": True})
        api.get_channels = AsyncMock(return_value=CHANNELS)
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    "servers": [
                        {"server": "svr1.supla.org", CONF_ACCESS_TOKEN: "token"}
                    ]
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    api.get_channels.side_effect = ClientError
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    api.get_channels.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_ON
