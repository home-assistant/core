"""Tests for the Foreca integration."""

from pyforeca import Observation
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.foreca.const import DOMAIN
from homeassistant.core import HomeAssistant


async def init_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Foreca integration for testing."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def load_observation(fixture: str) -> Observation:
    """Return the nearest station's observation from a recorded API response."""
    return Observation.from_api(
        load_json_object_fixture(fixture, DOMAIN)["observations"][0]
    )
