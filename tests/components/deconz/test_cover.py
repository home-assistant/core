"""deCONZ cover platform tests."""

from collections.abc import Callable
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType, WebsocketDataType

from tests.common import snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "0": {
                "name": "Window covering device",
                "type": "Window covering device",
                "state": {"lift": 100, "open": False, "reachable": True},
                "modelid": "lumi.curtain",
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "1": {
                "name": "Unsupported cover",
                "type": "Not a cover",
                "state": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
        }
    ],
)
async def test_cover(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    light_ws_data: WebsocketDataType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all supported cover entities are created."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.COVER]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Event signals cover is open

    await light_ws_data({"state": {"lift": 0, "open": True}})
    cover = hass.states.get("cover.window_covering_device")
    assert cover.state == CoverState.OPEN
    assert cover.attributes[ATTR_CURRENT_POSITION] == 100

    # Verify service calls for cover

    aioclient_mock = mock_put_request("/lights/0/state")

    # Service open cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.window_covering_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"open": True}

    # Service close cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.window_covering_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"open": False}

    # Service set cover position

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.window_covering_device", ATTR_POSITION: 40},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"lift": 60}

    # Service stop cover movement

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.window_covering_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {"stop": True}


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "etag": "87269755b9b3a046485fdae8d96b252c",
            "lastannounced": None,
            "lastseen": "2020-08-01T16:22:05Z",
            "manufacturername": "AXIS",
            "modelid": "Gear",
            "name": "Covering device",
            "state": {
                "bri": 0,
                "lift": 0,
                "on": False,
                "open": True,
                "reachable": True,
                "tilt": 0,
            },
            "swversion": "100-5.3.5.1122",
            "type": "Window covering device",
            "uniqueid": "00:24:46:00:00:12:34:56-01",
        }
    ],
)
async def test_tilt_cover(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    snapshot: SnapshotAssertion,
) -> None:
    """Test that tilting a cover works."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.COVER]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Verify service calls for tilting cover

    aioclient_mock = mock_put_request("/lights/0/state")

    # Service set tilt cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.covering_device", ATTR_TILT_POSITION: 40},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"tilt": 60}

    # Service open tilt cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.covering_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"tilt": 0}

    # Service close tilt cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.covering_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"tilt": 100}

    # Service stop cover movement

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.covering_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {"stop": True}


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "etag": "4cefc909134c8e99086b55273c2bde67",
            "hascolor": False,
            "lastannounced": "2022-08-08T12:06:18Z",
            "lastseen": "2022-08-14T14:22Z",
            "manufacturername": "Keen Home Inc",
            "modelid": "SV01-410-MP-1.0",
            "name": "Vent",
            "state": {
                "alert": "none",
                "bri": 242,
                "on": False,
                "reachable": True,
                "sat": 10,
            },
            "swversion": "0x00000012",
            "type": "Level controllable output",
            "uniqueid": "00:22:a3:00:00:00:00:00-01",
        }
    ],
)
async def test_level_controllable_output_cover(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    snapshot: SnapshotAssertion,
) -> None:
    """Test that tilting a cover works."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.COVER]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Verify service calls for tilting cover

    aioclient_mock = mock_put_request("/lights/0/state")

    # Service open cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.vent"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": False}

    # Service close cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.vent"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"on": True}

    # Service set cover position

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.vent", ATTR_POSITION: 40},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"bri": 152}

    # Service set tilt cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.vent", ATTR_TILT_POSITION: 40},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {"sat": 152}

    # Service open tilt cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.vent"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[5][2] == {"sat": 0}

    # Service close tilt cover

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.vent"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[6][2] == {"sat": 254}

    # Service stop cover movement

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.vent"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[7][2] == {"bri_inc": 0}
