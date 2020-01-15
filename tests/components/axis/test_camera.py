"""Axis camera platform tests."""

from homeassistant.components import axis
import homeassistant.components.camera as camera
from homeassistant.setup import async_setup_component

from .test_device import NAME, setup_axis_integration


async def test_platform_manually_configured(hass):
    """Test that nothing happens when platform is manually configured."""
    assert (
        await async_setup_component(
            hass, camera.DOMAIN, {"camera": {"platform": axis.DOMAIN}}
        )
        is True
    )

    assert axis.DOMAIN not in hass.data


async def test_camera(hass):
    """Test that Axis camera platform is loaded properly."""
    await setup_axis_integration(hass)

    assert len(hass.states.async_entity_ids("camera")) == 1

    cam = hass.states.get(f"camera.{NAME}")
    assert cam.state == "idle"
    assert cam.name == NAME
