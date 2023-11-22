"""The tests for the Ring switch platform."""
import requests_mock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import load_fixture


async def test_entity_registry(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.CAMERA)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("camera.front")
    assert entry.unique_id == 765432

    entry = entity_registry.async_get("camera.internal")
    assert entry.unique_id == 345678


async def test_camera_motion_detection_off_reports_correctly(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get("camera.front")
    assert state.attributes.get("motion_detection") is not True
    assert state.attributes.get("friendly_name") == "Front"


async def test_camera_motion_detection_on_reports_correctly(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get("camera.internal")
    assert state.attributes.get("motion_detection") is True
    assert state.attributes.get("friendly_name") == "Internal"


async def test_camera_motion_detection_can_be_turned_on(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Tests the siren turns on correctly."""
    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get("camera.front")
    assert state.attributes.get("motion_detection") is not True

    await hass.services.async_call(
        "camera",
        "enable_motion_detection",
        {"entity_id": "camera.front"},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get("camera.front")
    assert state.attributes.get("motion_detection") is True


async def test_updates_work(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Tests the update service works correctly."""
    await setup_platform(hass, Platform.CAMERA)
    state = hass.states.get("camera.internal")
    assert state.attributes.get("motion_detection") is True
    # Changes the return to indicate that the switch is now on.
    requests_mock.get(
        "https://api.ring.com/clients_api/ring_devices",
        text=load_fixture("devices_updated.json", "ring"),
    )

    await hass.services.async_call("ring", "update", {}, blocking=True)

    await hass.async_block_till_done()

    state = hass.states.get("camera.internal")
    assert state.attributes.get("motion_detection") is not True
