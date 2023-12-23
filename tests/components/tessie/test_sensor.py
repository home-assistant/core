"""Test the Tessie sensor platform."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_sensors(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests that the sensor entities are correct."""

    assert len(hass.states.async_all("sensor")) == 0

    await setup_platform(hass)

    assert hass.states.async_all("sensor") == snapshot(name="all")
