"""The tests for generic camera component."""
from datetime import timedelta
from http import HTTPStatus
import io

from homeassistant.config import async_process_ha_core_config
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_bad_posting(hass, hass_client_no_auth):
    """Test that posting to wrong api endpoint fails."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com"},
    )

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "platform": "push",
                "name": "config_test",
                "webhook_id": "camera.config_test",
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("camera.config_test") is not None

    client = await hass_client_no_auth()

    # missing file
    async with client.post("/api/webhook/camera.config_test") as resp:
        assert resp.status == HTTPStatus.OK  # webhooks always return OK

    camera_state = hass.states.get("camera.config_test")
    assert camera_state.state == "idle"  # no file supplied we are still idle


async def test_posting_url(hass, hass_client_no_auth):
    """Test that posting to api endpoint works."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com"},
    )

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "platform": "push",
                "name": "config_test",
                "webhook_id": "camera.config_test",
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    files = {"image": io.BytesIO(b"fake")}

    # initial state
    camera_state = hass.states.get("camera.config_test")
    assert camera_state.state == "idle"

    # post image
    resp = await client.post("/api/webhook/camera.config_test", data=files)
    assert resp.status == HTTPStatus.OK

    # state recording
    camera_state = hass.states.get("camera.config_test")
    assert camera_state.state == "recording"

    # await timeout
    shifted_time = dt_util.utcnow() + timedelta(seconds=15)
    async_fire_time_changed(hass, shifted_time)
    await hass.async_block_till_done()

    # back to initial state
    camera_state = hass.states.get("camera.config_test")
    assert camera_state.state == "idle"
