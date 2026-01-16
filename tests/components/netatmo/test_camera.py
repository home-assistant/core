"""The tests for Netatmo camera."""
# Webhook push_types MUST follow exactly Netatmo's naming on products!
# See https://dev.netatmo.com/apidocumentation
# e.g. cameras: NACamera, NOC, etc.

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pyatmo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import camera
from homeassistant.components.camera import CameraState
from homeassistant.components.netatmo.const import (
    NETATMO_EVENT,
    SERVICE_SET_CAMERA_LIGHT,
    SERVICE_SET_PERSON_AWAY,
    SERVICE_SET_PERSONS_HOME,
)
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .common import (
    fake_post_request,
    selected_platforms,
    simulate_webhook,
    snapshot_platform_entities,
)

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed


async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await snapshot_platform_entities(
            hass,
            config_entry,
            Platform.CAMERA,
            entity_registry,
            snapshot,
        )


@pytest.mark.parametrize(
    ("camera_type", "camera_id", "camera_entity"),
    [
        ("NACamera", "12:34:56:00:f1:62", "camera.hall"),
        ("NOC", "12:34:56:10:b9:0e", "camera.front"),
    ],
)
async def test_setup_component_with_webhook(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    camera_type: str,
    camera_id: str,
    camera_entity: str,
) -> None:
    """Test setup with webhook."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await hass.async_block_till_done()

    # Test on/off camera events
    assert hass.states.get(camera_entity).state == "streaming"
    response = {
        "event_type": "off",
        "device_id": camera_id,
        "camera_id": camera_id,
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": f"{camera_type}-off",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity).state == "idle"

    response = {
        "event_type": "on",
        "device_id": camera_id,
        "camera_id": camera_id,
        "event_id": "646227f1dc0dfa000ec5f350",
        "push_type": f"{camera_type}-on",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity).state == "streaming"

    # Test turn_on/turn_off services
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            "camera", "turn_off", service_data={"entity_id": camera_entity}
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": camera_id,
                        "monitoring": "off",
                    }
                ]
            }
        )

    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            "camera", "turn_on", service_data={"entity_id": camera_entity}
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": camera_id,
                        "monitoring": "on",
                    }
                ]
            }
        )


IMAGE_BYTES_FROM_STREAM = b"test stream image bytes"


async def test_camera_image_local(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test retrieval or local camera image."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    uri = "http://192.168.0.123/678460a0d47e5618699fb31169e2b47d"
    stream_uri = uri + "/live/files/high/index.m3u8"
    camera_entity_indoor = "camera.hall"
    cam = hass.states.get(camera_entity_indoor)

    assert cam is not None
    assert cam.state == CameraState.STREAMING
    assert cam.name == "Hall"

    stream_source = await camera.async_get_stream_source(hass, camera_entity_indoor)
    assert stream_source == stream_uri

    image = await camera.async_get_image(hass, camera_entity_indoor)

    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_camera_image_vpn(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test retrieval of remote camera image."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    uri = "https://prodvpn-eu-6.netatmo.net/10.20.30.41/333333333333/444444444444,,"
    stream_uri = uri + "/live/files/high/index.m3u8"
    camera_entity_indoor = "camera.front"
    cam = hass.states.get(camera_entity_indoor)

    assert cam is not None
    assert cam.state == CameraState.STREAMING

    stream_source = await camera.async_get_stream_source(hass, camera_entity_indoor)
    assert stream_source == stream_uri

    image = await camera.async_get_image(hass, camera_entity_indoor)
    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_service_set_person_away(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service to set person as away."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.hall",
        "person": "Richard Doe",
    }

    with patch("pyatmo.home.Home.async_set_persons_away") as mock_set_persons_away:
        await hass.services.async_call(
            "netatmo", SERVICE_SET_PERSON_AWAY, service_data=data
        )
        await hass.async_block_till_done()
        mock_set_persons_away.assert_called_once_with(
            person_id="91827376-7e04-5298-83af-a0cb8372dff3",
        )

    data = {
        "entity_id": "camera.hall",
    }

    with patch("pyatmo.home.Home.async_set_persons_away") as mock_set_persons_away:
        await hass.services.async_call(
            "netatmo", SERVICE_SET_PERSON_AWAY, service_data=data
        )
        await hass.async_block_till_done()
        mock_set_persons_away.assert_called_once_with(
            person_id=None,
        )


async def test_service_set_person_away_invalid_person(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service to set invalid person as away."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.hall",
        "person": "Batman",
    }

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            "netatmo",
            SERVICE_SET_PERSON_AWAY,
            service_data=data,
            blocking=True,
        )
    await hass.async_block_till_done()

    assert excinfo.value.args == ("Person(s) not registered ['Batman']",)


async def test_service_set_persons_home_invalid_person(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service to set invalid persons as home."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.hall",
        "persons": "Batman",
    }

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            "netatmo",
            SERVICE_SET_PERSONS_HOME,
            service_data=data,
            blocking=True,
        )
    await hass.async_block_till_done()

    assert excinfo.value.args == ("Person(s) not registered ['Batman']",)


async def test_service_set_persons_home(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service to set persons as home."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.hall",
        "persons": "John Doe",
    }

    with patch("pyatmo.home.Home.async_set_persons_home") as mock_set_persons_home:
        await hass.services.async_call(
            "netatmo", SERVICE_SET_PERSONS_HOME, service_data=data
        )
        await hass.async_block_till_done()
        mock_set_persons_home.assert_called_once_with(
            person_ids=["91827374-7e04-5298-83ad-a0cb8372dff1"],
        )


@pytest.mark.parametrize(
    ("camera_type", "camera_id", "camera_entity"),
    [
        ("NOC", "12:34:56:10:b9:0e", "camera.front"),
    ],
)
async def test_light_component_with_webhook(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    camera_type: str,
    camera_id: str,
    camera_entity: str,
) -> None:
    """Test setup with webhook."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await hass.async_block_till_done()

    assert hass.states.get(camera_entity).state == "streaming"

    response = {
        "event_type": "light_mode",
        "device_id": camera_id,
        "camera_id": camera_id,
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": f"{camera_type}-light_mode",
        "sub_type": "on",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity).state == "streaming"
    assert hass.states.get(camera_entity).attributes["light_state"] == "on"

    response = {
        "event_type": "light_mode",
        "device_id": camera_id,
        "camera_id": camera_id,
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": f"{camera_type}-light_mode",
        "sub_type": "auto",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity).attributes["light_state"] == "auto"

    response = {
        "event_type": "light_mode",
        "device_id": camera_id,
        "camera_id": camera_id,
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": f"{camera_type}-light_mode",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity).state == "streaming"
    assert hass.states.get(camera_entity).attributes["light_state"] == "auto"


async def test_service_set_camera_light(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service to set the outdoor camera light mode."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.front",
        "camera_light_mode": "on",
    }

    expected_data = {
        "modules": [
            {
                "id": "12:34:56:10:b9:0e",
                "floodlight": "on",
            },
        ],
    }
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            "netatmo", SERVICE_SET_CAMERA_LIGHT, service_data=data
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(expected_data)


async def test_service_set_camera_light_invalid_type(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service to set the indoor camera light mode."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.hall",
        "camera_light_mode": "on",
    }

    with (
        patch("pyatmo.home.Home.async_set_state") as mock_set_state,
        pytest.raises(HomeAssistantError) as excinfo,
    ):
        await hass.services.async_call(
            "netatmo",
            SERVICE_SET_CAMERA_LIGHT,
            service_data=data,
            blocking=True,
        )
    await hass.async_block_till_done()

    mock_set_state.assert_not_called()
    assert "NACamera <Hall> does not have a floodlight" in excinfo.value.args[0]


@pytest.mark.parametrize(
    ("camera_type", "camera_id", "camera_entity"),
    [
        ("NACamera", "12:34:56:00:f1:62", "camera.hall"),
        ("NOC", "12:34:56:10:b9:0e", "camera.front"),
    ],
)
async def test_camera_reconnect_webhook(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    camera_type: str,
    camera_id: str,
    camera_entity: str,
) -> None:
    """Test webhook event on camera reconnect."""
    fake_post_hits = 0

    async def fake_post(*args: Any, **kwargs: Any):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch("homeassistant.components.netatmo.data_handler.PLATFORMS", ["camera"]),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ) as mock_webhook,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        mock_webhook.return_value = "https://example.com"
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        webhook_id = config_entry.data[CONF_WEBHOOK_ID]

        # Fake webhook activation
        response = {
            "push_type": "webhook_activation",
        }
        await simulate_webhook(hass, webhook_id, response)
        await hass.async_block_till_done()

        assert fake_post_hits == 8

        calls = fake_post_hits

        # Fake camera reconnect
        response = {
            "push_type": f"{camera_type}-connection",
        }
        await simulate_webhook(hass, webhook_id, response)
        await hass.async_block_till_done()

        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=60),
        )
        await hass.async_block_till_done()
        assert fake_post_hits >= calls

        # Real camera disconnect
        assert hass.states.get(camera_entity).state == "streaming"
        response = {
            "event_type": "disconnection",
            "device_id": camera_id,
            "camera_id": camera_id,
            "event_id": "601dce1560abca1ebad9b723",
            "push_type": f"{camera_type}-disconnection",
        }
        await simulate_webhook(hass, webhook_id, response)

        assert hass.states.get(camera_entity).state == "idle"

        response = {
            "event_type": "connection",
            "device_id": camera_id,
            "camera_id": camera_id,
            "event_id": "646227f1dc0dfa000ec5f350",
            "push_type": f"{camera_type}-connection",
        }
        await simulate_webhook(hass, webhook_id, response)

        assert hass.states.get(camera_entity).state == "streaming"


@pytest.mark.parametrize(
    ("camera_type", "camera_id", "camera_entity", "home_id"),
    [
        # From the fixture the following combination is the only right one
        # camera_type, camera_id, camera_entity, home_id
        # "NOC", "12:34:56:10:b9:0e", "camera.front", "91763b24c43d3e344f424e8b"
        # will test all the wrong combinations to be sure that the validation works
        # Test1: wrong home_id
        ("NOC", "12:34:56:10:b9:0e", "camera.front", "91763b24c43d3e344f424e80"),
        # Test2: wrong camera_type (will result incorrect push_type)
        ("NACamera", "12:34:56:10:b9:0e", "camera.front", "91763b24c43d3e344f424e8b"),
        # Test3: wrong camera_id (id of NACamera)
        ("NOC", "12:34:56:00:f1:62", "camera.front", "91763b24c43d3e344f424e8b"),
        # Test4: missing camera_type (will result missing push_type)
        (None, "12:34:56:10:b9:0e", "camera.front", "91763b24c43d3e344f424e8b"),
        # Test5: missing camera_id
        ("NOC", None, "camera.front", "91763b24c43d3e344f424e8b"),
        # Note: missing home_id is not possible as it's mandatory in the webhook payload
        # (by experience it is filled by some logic even if missing)
    ],
)
async def test_camera_webhook_consistency(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    camera_type: str,
    camera_id: str,
    camera_entity: str,
    home_id: str,
) -> None:
    """Test webhook event on camera reconnect."""
    fake_post_hits = 0

    async def fake_post(*args: Any, **kwargs: Any):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch("homeassistant.components.netatmo.data_handler.PLATFORMS", ["camera"]),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ) as mock_webhook,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        mock_webhook.return_value = "https://example.com"
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        webhook_id = config_entry.data[CONF_WEBHOOK_ID]

        # Fake webhook activation
        response = {
            "push_type": "webhook_activation",
        }
        await simulate_webhook(hass, webhook_id, response)
        await hass.async_block_till_done()

        assert fake_post_hits == 8

        calls = fake_post_hits

        # Fake camera reconnect
        if camera_type is None:
            response = {
                "event_type": "disconnection",
                "home_id": home_id,
                "device_id": camera_id,
                "camera_id": camera_id,
            }
        elif camera_id is None:
            response = {
                "event_type": "disconnection",
                "home_id": home_id,
                "device_id": camera_id,
                "push_type": f"{camera_type}-disconnection",
            }
        else:
            response = {
                "event_type": "disconnection",
                "home_id": home_id,
                "device_id": camera_id,
                "camera_id": camera_id,
                "push_type": f"{camera_type}-disconnection",
            }
        await simulate_webhook(hass, webhook_id, response)
        await hass.async_block_till_done()

        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=60),
        )
        await hass.async_block_till_done()
        assert fake_post_hits >= calls

        assert hass.states.get(camera_entity).state == "streaming"


async def test_webhook_person_event(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test that person events are handled."""
    with selected_platforms(["camera"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    test_netatmo_event = async_capture_events(hass, NETATMO_EVENT)
    assert not test_netatmo_event

    fake_webhook_event = {
        "persons": [
            {
                "id": "91827374-7e04-5298-83ad-a0cb8372dff1",
                "face_id": "a1b2c3d4e5",
                "face_key": "9876543",
                "is_known": True,
                "face_url": "https://netatmocameraimage.blob.core.windows.net/production/12345",
            }
        ],
        "snapshot_id": "123456789abc",
        "snapshot_key": "foobar123",
        "snapshot_url": "https://netatmocameraimage.blob.core.windows.net/production/12346",
        "event_type": "person",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:f1:62",
        "event_id": "1234567890",
        "message": "MYHOME: John Doe has been seen by Indoor Camera ",
        "push_type": "NACamera-person",
    }

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, fake_webhook_event)

    assert test_netatmo_event


async def test_setup_component_no_devices(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup with no devices."""
    fake_post_hits = 0

    async def fake_post_no_data(*args, **kwargs):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch("homeassistant.components.netatmo.data_handler.PLATFORMS", ["camera"]),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post_no_data
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert fake_post_hits == 8


async def test_camera_image_raises_exception(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup with no devices."""
    fake_post_hits = 0

    async def fake_post(*args: Any, **kwargs: Any):
        """Return fake data."""
        nonlocal fake_post_hits
        fake_post_hits += 1

        if "endpoint" not in kwargs:
            return "{}"

        endpoint = kwargs["endpoint"].split("/")[-1]

        if "snapshot_720.jpg" in endpoint:
            raise pyatmo.ApiError

        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch("homeassistant.components.netatmo.data_handler.PLATFORMS", ["camera"]),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_get_image.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    camera_entity_indoor = "camera.hall"

    with pytest.raises(Exception) as excinfo:
        await camera.async_get_image(hass, camera_entity_indoor)

    assert excinfo.value.args == ("Unable to get image",)
    assert fake_post_hits == 9
