"""Test the Tessie binary sensor platform."""
from syrupy import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_binary_sensors(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests that the binary sensor entities are correct."""

    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 0

    await setup_platform(hass)

    assert hass.states.async_all(BINARY_SENSOR_DOMAIN) == snapshot(name="all")
