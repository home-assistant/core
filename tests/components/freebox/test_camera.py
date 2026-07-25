"""Tests for the Freebox cameras."""

from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    SERVICE_DISABLE_MOTION,
    SERVICE_ENABLE_MOTION,
)
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_platform
from .const import DATA_HOME_GET_NODES

from tests.common import async_fire_time_changed


async def test_setup(hass: HomeAssistant, router: Mock) -> None:
    """Test camera entities are created and reflect node status."""
    await setup_platform(hass, CAMERA_DOMAIN)

    state_i = hass.states.get("camera.camera_i")
    state_ii = hass.states.get("camera.camera_ii")
    assert state_i is not None
    assert state_ii is not None
    # Both fixtures have status=active, the entity reports streaming.
    assert state_i.state == "streaming"
    assert state_ii.state == "streaming"


async def test_label_change_propagates(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    router: Mock,
) -> None:
    """Test camera label changes from the API update the device registry."""
    await setup_platform(hass, CAMERA_DOMAIN)

    camera_node_id = 15  # Caméra I from fixture
    device = device_registry.async_get_device(identifiers={(DOMAIN, camera_node_id)})
    assert device is not None
    assert device.name == "Caméra I"

    updated_nodes = deepcopy(DATA_HOME_GET_NODES)
    for node in updated_nodes:
        if node["id"] == camera_node_id:
            node["label"] = "Caméra entrée"
            break
    router().home.get_home_nodes.return_value = updated_nodes

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, camera_node_id)})
    assert device is not None
    assert device.name == "Caméra entrée"


async def test_status_change_updates_streaming(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    router: Mock,
) -> None:
    """Test the streaming state reflects API status changes on update."""
    await setup_platform(hass, CAMERA_DOMAIN)

    assert hass.states.get("camera.camera_i").state == "streaming"

    updated_nodes = deepcopy(DATA_HOME_GET_NODES)
    for node in updated_nodes:
        if node["id"] == 15:
            node["status"] = "inactive"
            break
    router().home.get_home_nodes.return_value = updated_nodes

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("camera.camera_i").state == "idle"


async def test_motion_detection_toggle(
    hass: HomeAssistant,
    router: Mock,
) -> None:
    """Test enabling and disabling motion detection on the camera."""
    await setup_platform(hass, CAMERA_DOMAIN)

    await hass.services.async_call(
        CAMERA_DOMAIN,
        SERVICE_DISABLE_MOTION,
        service_data={ATTR_ENTITY_ID: "camera.camera_i"},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(15, 0, {"value": False})

    await hass.services.async_call(
        CAMERA_DOMAIN,
        SERVICE_ENABLE_MOTION,
        service_data={ATTR_ENTITY_ID: "camera.camera_i"},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(15, 0, {"value": True})
