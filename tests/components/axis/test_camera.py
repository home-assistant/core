"""Axis camera platform tests."""

from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.setup import async_setup_component

from .test_device import NAME, setup_axis_integration


async def test_platform_manually_configured(hass):
    """Test that nothing happens when platform is manually configured."""
    assert (
        await async_setup_component(
            hass, CAMERA_DOMAIN, {"camera": {"platform": AXIS_DOMAIN}}
        )
        is True
    )

    assert AXIS_DOMAIN not in hass.data


async def test_camera(hass):
    """Test that Axis camera platform is loaded properly."""
    await setup_axis_integration(hass)

    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 1

    cam = hass.states.get(f"camera.{NAME}")
    assert cam.state == "idle"
    assert cam.name == NAME
