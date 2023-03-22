"""The tests for the TTS component."""
import pytest
import yarl

import homeassistant.components.media_player as media_player
from homeassistant.components.media_player import (
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.notify as notify
import homeassistant.components.tts as tts
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service


def relative_url(url):
    """Convert an absolute url to a relative one."""
    return str(yarl.URL(url).relative())


@pytest.fixture(autouse=True)
async def internal_url_mock(hass):
    """Mock internal URL of the instance."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )


async def test_setup_platform(hass: HomeAssistant) -> None:
    """Set up the tts platform ."""
    config = {
        notify.DOMAIN: {
            "platform": "tts",
            "name": "tts_test",
            "tts_service": "tts.demo_say",
            "media_player": "media_player.demo",
        }
    }
    with assert_setup_component(1, notify.DOMAIN):
        assert await async_setup_component(hass, notify.DOMAIN, config)

    assert hass.services.has_service(notify.DOMAIN, "tts_test")


async def test_setup_component_and_test_service(hass: HomeAssistant) -> None:
    """Set up the demo platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {
        tts.DOMAIN: {"platform": "demo"},
        media_player.DOMAIN: {"platform": "demo"},
        notify.DOMAIN: {
            "platform": "tts",
            "name": "tts_test",
            "tts_service": "tts.demo_say",
            "media_player": "media_player.demo",
            "language": "en",
        },
    }

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    with assert_setup_component(1, notify.DOMAIN):
        assert await async_setup_component(hass, notify.DOMAIN, config)

    await hass.services.async_call(
        notify.DOMAIN,
        "tts_test",
        {
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )

    await hass.async_block_till_done()

    assert len(calls) == 1
