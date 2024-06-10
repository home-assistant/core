"""The tests for the Ring switch platform."""

from unittest.mock import PropertyMock

import pytest
import ring_doorbell

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ring_client,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.CAMERA)

    entry = entity_registry.async_get("camera.front")
    assert entry.unique_id == "765432"

    entry = entity_registry.async_get("camera.internal")
    assert entry.unique_id == "345678"


@pytest.mark.parametrize(
    ("entity_name", "expected_state", "friendly_name"),
    [
        ("camera.internal", True, "Internal"),
        ("camera.front", None, "Front"),
    ],
    ids=["On", "Off"],
)
async def test_camera_motion_detection_state_reports_correctly(
    hass: HomeAssistant,
    mock_ring_client,
    entity_name,
    expected_state,
    friendly_name,
) -> None:
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get(entity_name)
    assert state.attributes.get("motion_detection") is expected_state
    assert state.attributes.get("friendly_name") == friendly_name


async def test_camera_motion_detection_can_be_turned_on(
    hass: HomeAssistant, mock_ring_client
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
    hass: HomeAssistant, mock_ring_client, mock_ring_devices
) -> None:
    """Tests the update service works correctly."""
    await setup_platform(hass, Platform.CAMERA)
    state = hass.states.get("camera.internal")
    assert state.attributes.get("motion_detection") is True

    internal_camera_mock = mock_ring_devices.get_device(345678)
    internal_camera_mock.motion_detection = False

    await hass.services.async_call("ring", "update", {}, blocking=True)

    await hass.async_block_till_done()

    state = hass.states.get("camera.internal")
    assert state.attributes.get("motion_detection") is not True


@pytest.mark.parametrize(
    ("exception_type", "reauth_expected"),
    [
        (ring_doorbell.AuthenticationError, True),
        (ring_doorbell.RingTimeout, False),
        (ring_doorbell.RingError, False),
    ],
    ids=["Authentication", "Timeout", "Other"],
)
async def test_motion_detection_errors_when_turned_on(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    exception_type,
    reauth_expected,
) -> None:
    """Tests the motion detection errors are handled correctly."""
    await setup_platform(hass, Platform.CAMERA)
    config_entry = hass.config_entries.async_entries("ring")[0]

    assert not any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    front_camera_mock = mock_ring_devices.get_device(765432)
    p = PropertyMock(side_effect=exception_type)
    type(front_camera_mock).motion_detection = p

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "camera",
            "enable_motion_detection",
            {"entity_id": "camera.front"},
            blocking=True,
        )
    await hass.async_block_till_done()
    p.assert_called_once()
    assert (
        any(
            flow
            for flow in config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
            if flow["handler"] == "ring"
        )
        == reauth_expected
    )
