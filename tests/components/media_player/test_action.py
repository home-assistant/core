"""Test media player actions."""

import pytest
import voluptuous as vol

from homeassistant.core import Context
from homeassistant.helpers.script import Script, async_validate_actions_config

from tests.common import async_mock_service


@pytest.mark.parametrize(
    "config",
    [
        {
            "media_player.not_supported": {},
        },
        {
            "media_player.play_media": {
                "entity_id": "not_media_player.not_supported",
                "media_content_id": "youtube:video:123",
                "media_content_type": "movie",
            },
        },
    ],
)
async def test_play_media_validate_action(hass, config):
    """Test validate play media config."""
    with pytest.raises(vol.Invalid):
        await async_validate_actions_config(
            hass,
            [config],
        )


async def test_play_media_run_action(hass):
    """Test run play media action."""
    calls = async_mock_service(hass, "media_player", "play_media")
    config = await async_validate_actions_config(
        hass,
        [
            {
                "media_player.play_media": {
                    "entity_id": "media_player.test",
                    "media_content_id": "youtube:video:123",
                    "media_content_type": "movie",
                }
            }
        ],
    )
    script = Script(hass, config, "Test Script", "test")
    context = Context()
    await script.async_run(context=context)
    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "media_player.test",
        "media_content_id": "youtube:video:123",
        "media_content_type": "movie",
    }
    assert calls[0].context is context
