"""Tests for the air-Q integration."""

from unittest.mock import patch

from homeassistant.components.airq.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .common import TEST_DEVICE_INFO, TEST_USER_DATA

from tests.common import MockConfigEntry


async def setup_platform(hass: HomeAssistant, platform: Platform) -> None:
    """Load AirQ integration.

    This function does not patch AirQ itself, rather it depends on being
    run in presence of `mock_coordinator_airq` fixture, which patches calls
    by `AirQCoordinator.airq`, which are done under `async_setup`.

    Patching airq.PLATFORMS allows to set up a single platform in isolation.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_USER_DATA, unique_id=TEST_DEVICE_INFO["id"]
    )
    config_entry.add_to_hass(hass)

    # The patching is now handled by the mock_airq fixture.
    # We just need to load the component.
    with patch("homeassistant.components.airq.PLATFORMS", [platform]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
