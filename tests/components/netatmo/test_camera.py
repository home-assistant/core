"""The tests for Netatmo camera."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pyatmo
import pytest

from homeassistant.components import camera
from homeassistant.components.camera import STATE_STREAMING
from homeassistant.components.netatmo.const import (
    NETATMO_EVENT,
    SERVICE_SET_CAMERA_LIGHT,
    SERVICE_SET_PERSON_AWAY,
    SERVICE_SET_PERSONS_HOME,
)
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt

from .common import fake_post_request, selected_platforms, simulate_webhook

from tests.common import async_capture_events, async_fire_time_changed


async def test_setup_component_with_webhook(hass, config_entry, netatmo_auth):
    """Test setup with webhook."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await hass.async_block_till_done()

    camera_entity_indoor = "camera.hall"
    camera_entity_outdoor = "camera.garden"
    assert hass.states.get(camera_entity_indoor).state == "streaming"
    response = {
        "event_type": "off",
        "device_id": "12:34:56:00:f1:62",
        "camera_id": "12:34:56:00:f1:62",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NACamera-off",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity_indoor).state == "idle"

    response = {
        "event_type": "on",
        "device_id": "12:34:56:00:f1:62",
        "camera_id": "12:34:56:00:f1:62",
        "event_id": "646227f1dc0dfa000ec5f350",
        "push_type": "NACamera-on",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity_indoor).state == "streaming"

    response = {
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "camera_id": "12:34:56:00:a5:a4",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NOC-light_mode",
        "sub_type": "on",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity_outdoor).state == "streaming"
    assert hass.states.get(camera_entity_outdoor).attributes["light_state"] == "on"

    response = {
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "camera_id": "12:34:56:00:a5:a4",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NOC-light_mode",
        "sub_type": "auto",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity_outdoor).attributes["light_state"] == "auto"

    response = {
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NOC-light_mode",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(camera_entity_indoor).state == "streaming"
    assert hass.states.get(camera_entity_outdoor).attributes["light_state"] == "auto"

    with patch("pyatmo.camera.AsyncCameraData.async_set_state") as mock_set_state:
        await hass.services.async_call(
            "camera", "turn_off", service_data={"entity_id": "camera.hall"}
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            home_id="91763b24c43d3e344f424e8b",
            camera_id="12:34:56:00:f1:62",
            monitoring="off",
        )

    with patch("pyatmo.camera.AsyncCameraData.async_set_state") as mock_set_state:
        await hass.services.async_call(
            "camera", "turn_on", service_data={"entity_id": "camera.hall"}
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            home_id="91763b24c43d3e344f424e8b",
            camera_id="12:34:56:00:f1:62",
            monitoring="on",
        )


IMAGE_BYTES_FROM_STREAM = b"test stream image bytes"


async def test_camera_image_local(hass, config_entry, requests_mock, netatmo_auth):
    """Test retrieval or local camera image."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    uri = "http://192.168.0.123/678460a0d47e5618699fb31169e2b47d"
    stream_uri = uri + "/live/files/high/index.m3u8"
    camera_entity_indoor = "camera.hall"
    cam = hass.states.get(camera_entity_indoor)

    assert cam is not None
    assert cam.state == STATE_STREAMING

    stream_source = await camera.async_get_stream_source(hass, camera_entity_indoor)
    assert stream_source == stream_uri

    requests_mock.get(
        uri + "/live/snapshot_720.jpg",
        content=IMAGE_BYTES_FROM_STREAM,
    )
    image = await camera.async_get_image(hass, camera_entity_indoor)
    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_camera_image_vpn(hass, config_entry, requests_mock, netatmo_auth):
    """Test retrieval of remote camera image."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    uri = (
        "https://prodvpn-eu-2.netatmo.net/restricted/10.255.248.91/"
        "6d278460699e56180d47ab47169efb31/MpEylTU2MDYzNjRVD-LJxUnIndumKzLboeAwMDqTTw,,"
    )
    stream_uri = uri + "/live/files/high/index.m3u8"
    camera_entity_indoor = "camera.garden"
    cam = hass.states.get(camera_entity_indoor)

    assert cam is not None
    assert cam.state == STATE_STREAMING

    stream_source = await camera.async_get_stream_source(hass, camera_entity_indoor)
    assert stream_source == stream_uri

    requests_mock.get(
        uri + "/live/snapshot_720.jpg",
        content=IMAGE_BYTES_FROM_STREAM,
    )
    image = await camera.async_get_image(hass, camera_entity_indoor)
    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_service_set_person_away(hass, config_entry, netatmo_auth):
    """Test service to set person as away."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.hall",
        "person": "Richard Doe",
    }

    with patch(
        "pyatmo.camera.AsyncCameraData.async_set_persons_away"
    ) as mock_set_persons_away:
        await hass.services.async_call(
            "netatmo", SERVICE_SET_PERSON_AWAY, service_data=data
        )
        await hass.async_block_till_done()
        mock_set_persons_away.assert_called_once_with(
            person_id="91827376-7e04-5298-83af-a0cb8372dff3",
            home_id="91763b24c43d3e344f424e8b",
        )

    data = {
        "entity_id": "camera.hall",
    }

    with patch(
        "pyatmo.camera.AsyncCameraData.async_set_persons_away"
    ) as mock_set_persons_away:
        await hass.services.async_call(
            "netatmo", SERVICE_SET_PERSON_AWAY, service_data=data
        )
        await hass.async_block_till_done()
        mock_set_persons_away.assert_called_once_with(
            person_id=None,
            home_id="91763b24c43d3e344f424e8b",
        )


async def test_service_set_person_away_invalid_person(hass, config_entry, netatmo_auth):
    """Test service to set invalid person as away."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

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
    hass, config_entry, netatmo_auth
):
    """Test service to set invalid persons as home."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

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


async def test_service_set_persons_home(hass, config_entry, netatmo_auth):
    """Test service to set persons as home."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.hall",
        "persons": "John Doe",
    }

    with patch(
        "pyatmo.camera.AsyncCameraData.async_set_persons_home"
    ) as mock_set_persons_home:
        await hass.services.async_call(
            "netatmo", SERVICE_SET_PERSONS_HOME, service_data=data
        )
        await hass.async_block_till_done()
        mock_set_persons_home.assert_called_once_with(
            person_ids=["91827374-7e04-5298-83ad-a0cb8372dff1"],
            home_id="91763b24c43d3e344f424e8b",
        )


async def test_service_set_camera_light(hass, config_entry, netatmo_auth):
    """Test service to set the outdoor camera light mode."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.garden",
        "camera_light_mode": "on",
    }

    with patch("pyatmo.camera.AsyncCameraData.async_set_state") as mock_set_state:
        await hass.services.async_call(
            "netatmo", SERVICE_SET_CAMERA_LIGHT, service_data=data
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            home_id="91763b24c43d3e344f424e8b",
            camera_id="12:34:56:00:a5:a4",
            floodlight="on",
        )


async def test_camera_reconnect_webhook(hass, config_entry):
    """Test webhook event on camera reconnect."""
    fake_post_hits = 0

    async def fake_post(*args, **kwargs):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(*args, **kwargs)

    with patch(
        "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.components.netatmo.PLATFORMS", ["camera"]
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.netatmo.webhook_generate_url"
    ) as mock_webhook:
        mock_auth.return_value.async_post_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        mock_webhook.return_value = "https://example.com"
        await hass.config_entries.async_setup(config_entry.entry_id)

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
            "push_type": "NACamera-connection",
        }
        await simulate_webhook(hass, webhook_id, response)
        await hass.async_block_till_done()

        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(seconds=60),
        )
        await hass.async_block_till_done()
        assert fake_post_hits > calls


async def test_webhook_person_event(hass, config_entry, netatmo_auth):
    """Test that person events are handled."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

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


async def test_setup_component_no_devices(hass, config_entry):
    """Test setup with no devices."""
    fake_post_hits = 0

    async def fake_post_no_data(*args, **kwargs):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return "{}"

    with patch(
        "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.components.netatmo.PLATFORMS", ["camera"]
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.netatmo.webhook_generate_url"
    ):
        mock_auth.return_value.async_post_request.side_effect = fake_post_no_data
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert fake_post_hits == 4


async def test_camera_image_raises_exception(hass, config_entry, requests_mock):
    """Test setup with no devices."""
    fake_post_hits = 0

    async def fake_post(*args, **kwargs):
        """Return fake data."""
        nonlocal fake_post_hits
        fake_post_hits += 1

        if "url" not in kwargs:
            return "{}"

        endpoint = kwargs["url"].split("/")[-1]

        if "snapshot_720.jpg" in endpoint:
            raise pyatmo.exceptions.ApiError()

        return await fake_post_request(*args, **kwargs)

    with patch(
        "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.components.netatmo.PLATFORMS", ["camera"]
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.netatmo.webhook_generate_url"
    ):
        mock_auth.return_value.async_post_request.side_effect = fake_post
        mock_auth.return_value.async_get_image.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    camera_entity_indoor = "camera.hall"

    with pytest.raises(Exception) as excinfo:
        await camera.async_get_image(hass, camera_entity_indoor)

    assert excinfo.value.args == ("Unable to get image",)
    assert fake_post_hits == 9
