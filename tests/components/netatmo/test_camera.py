"""The tests for Netatmo device triggers."""
from freezegun import freeze_time

from homeassistant.components import camera
from homeassistant.components.camera import STATE_STREAMING
from homeassistant.components.netatmo.const import (
    SERVICE_SET_CAMERA_LIGHT,
    SERVICE_SET_PERSON_AWAY,
    SERVICE_SET_PERSONS_HOME,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send


@freeze_time("2019-06-16")
async def test_setup_component_with_webhook(hass, camera_entry):
    """Test ."""
    await hass.async_block_till_done()

    camera_entity_indoor = "camera.netatmo_hall"
    camera_entity_outdoor = "camera.netatmo_garden"
    assert hass.states.get(camera_entity_indoor).state == "streaming"
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8d",
        "event_type": "off",
        "device_id": "12:34:56:00:f1:62",
        "home_id": "91763b24c43d3e344f424e8b",
        "home_name": "LXMBRG",
        "camera_id": "12:34:56:00:f1:62",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NACamera-off",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-off",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(camera_entity_indoor).state == "idle"

    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8d",
        "event_type": "on",
        "device_id": "12:34:56:00:f1:62",
        "home_id": "91763b24c43d3e344f424e8b",
        "home_name": "LXMBRG",
        "camera_id": "12:34:56:00:f1:62",
        "event_id": "646227f1dc0dfa000ec5f350",
        "push_type": "NACamera-on",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-on",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(camera_entity_indoor).state == "streaming"

    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8d",
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "home_id": "91763b24c43d3e344f424e8b",
        "home_name": "LXMBRG",
        "camera_id": "12:34:56:00:a5:a4",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NOC-light_mode",
        "sub_type": "on",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-light_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(camera_entity_indoor).state == "streaming"
    assert hass.states.get(camera_entity_outdoor).attributes["light_state"] == "on"

    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8d",
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "home_id": "91763b24c43d3e344f424e8b",
        "home_name": "LXMBRG",
        "camera_id": "12:34:56:00:a5:a4",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NOC-light_mode",
        "sub_type": "auto",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-light_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(camera_entity_outdoor).attributes["light_state"] == "auto"

    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8d",
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "home_id": "91763b24c43d3e344f424e8b",
        "home_name": "LXMBRG",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NOC-light_mode",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-light_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(camera_entity_indoor).state == "streaming"
    assert hass.states.get(camera_entity_outdoor).attributes["light_state"] == "auto"


IMAGE_BYTES_FROM_STREAM = b"test stream image bytes"


async def test_camera_image_local(hass, camera_entry, requests_mock):
    """Test ."""
    await hass.async_block_till_done()

    uri = "http://192.168.0.123/678460a0d47e5618699fb31169e2b47d"
    stream_uri = uri + "/live/files/high/index.m3u8"
    camera_entity_indoor = "camera.netatmo_hall"
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


async def test_camera_image_vpn(hass, camera_entry, requests_mock):
    """Test ."""
    await hass.async_block_till_done()

    uri = "https://prodvpn-eu-2.netatmo.net/restricted/10.255.248.91/6d278460699e56180d47ab47169efb31/MpEylTU2MDYzNjRVD-LJxUnIndumKzLboeAwMDqTTw,,"
    stream_uri = uri + "/live/files/high/index.m3u8"
    camera_entity_indoor = "camera.netatmo_garden"
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


async def test_service_set_person_away(hass, camera_entry, caplog):
    """Test ."""
    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.netatmo_hall",
        "person": "Richard Doe",
    }

    await hass.services.async_call(
        "netatmo", SERVICE_SET_PERSON_AWAY, service_data=data
    )
    await hass.async_block_till_done()

    assert "Set Richard Doe as away" in caplog.text

    data = {
        "entity_id": "camera.netatmo_hall",
    }

    await hass.services.async_call(
        "netatmo", SERVICE_SET_PERSON_AWAY, service_data=data
    )
    await hass.async_block_till_done()

    assert "Set home as empty" in caplog.text


async def test_service_set_persons_home(hass, camera_entry, caplog):
    """Test ."""
    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.netatmo_hall",
        "persons": "John Doe",
    }

    await hass.services.async_call(
        "netatmo", SERVICE_SET_PERSONS_HOME, service_data=data
    )
    await hass.async_block_till_done()

    assert "Set ['John Doe'] as at home" in caplog.text


async def test_service_set_camera_light(hass, camera_entry, caplog):
    """Test ."""
    await hass.async_block_till_done()

    data = {
        "entity_id": "camera.netatmo_garden",
        "camera_light_mode": "on",
    }

    await hass.services.async_call(
        "netatmo", SERVICE_SET_CAMERA_LIGHT, service_data=data
    )
    await hass.async_block_till_done()

    assert "Turn camera light for 'Netatmo Garden' on" in caplog.text
