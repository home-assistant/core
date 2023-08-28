"""The tests for the TTS component."""
from unittest.mock import patch

import pytest

from homeassistant.components import notify, tts
from homeassistant.components.media_player import (
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import MockTTSEntity, mock_config_entry_setup

from tests.common import assert_setup_component, async_mock_service


@pytest.fixture(autouse=True)
async def internal_url_mock(hass: HomeAssistant) -> None:
    """Mock internal URL of the instance."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )


@pytest.fixture(autouse=True)
async def disable_platforms() -> None:
    """Disable demo platforms."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [],
    ):
        yield


async def test_setup_legacy_platform(hass: HomeAssistant) -> None:
    """Set up the tts notify platform ."""
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


async def test_setup_platform(hass: HomeAssistant) -> None:
    """Set up the tts notify platform ."""
    config = {
        notify.DOMAIN: {
            "platform": "tts",
            "name": "tts_test",
            "entity_id": "tts.test",
            "media_player": "media_player.demo",
        }
    }
    with assert_setup_component(1, notify.DOMAIN):
        assert await async_setup_component(hass, notify.DOMAIN, config)

    assert hass.services.has_service(notify.DOMAIN, "tts_test")


async def test_setup_platform_missing_key(hass: HomeAssistant) -> None:
    """Test platform without required tts_service or entity_id key."""
    config = {
        notify.DOMAIN: {
            "platform": "tts",
            "name": "tts_test",
            "media_player": "media_player.demo",
        }
    }
    with assert_setup_component(0, notify.DOMAIN):
        assert await async_setup_component(hass, notify.DOMAIN, config)

    assert not hass.services.has_service(notify.DOMAIN, "tts_test")


async def test_setup_legacy_service(hass: HomeAssistant) -> None:
    """Set up the demo platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {
        tts.DOMAIN: {"platform": "demo"},
        notify.DOMAIN: {
            "platform": "tts",
            "name": "tts_test",
            "tts_service": "tts.demo_say",
            "media_player": "media_player.demo",
            "language": "en",
        },
    }

    await async_setup_component(hass, "homeassistant", {})

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


async def test_setup_service(
    hass: HomeAssistant, mock_tts_entity: MockTTSEntity
) -> None:
    """Set up platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {
        notify.DOMAIN: {
            "platform": "tts",
            "name": "tts_test",
            "entity_id": "tts.test",
            "media_player": "media_player.demo",
            "language": "en_US",
        },
    }

    await mock_config_entry_setup(hass, mock_tts_entity)

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
