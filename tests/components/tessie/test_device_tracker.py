"""Test the Tessie device tracker platform."""

from syrupy import SnapshotAssertion

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_device_tracker(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests that the device tracker entities are correct."""

    assert len(hass.states.async_all(DEVICE_TRACKER_DOMAIN)) == 0

    await setup_platform(hass)

    assert hass.states.async_all(DEVICE_TRACKER_DOMAIN) == snapshot(name="all")
