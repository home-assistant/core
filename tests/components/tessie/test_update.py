"""Test the Tessie update platform."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_updates(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests that update entity is correct."""

    assert len(hass.states.async_all("update")) == 0

    await setup_platform(hass)

    assert hass.states.async_all("update") == snapshot(name="all")
