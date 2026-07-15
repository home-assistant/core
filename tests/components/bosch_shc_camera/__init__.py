"""Tests for the Bosch Smart Home Camera integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Fixed public OSS OAuth2 client (see config_flow.py) — identical in every
# Android APK, not a secret, safe to hardcode in tests.
TEST_CLIENT_ID = "oss_residential_app"

TEST_BEARER_TOKEN = "test-bearer-token"
TEST_REFRESH_TOKEN = "test-refresh-token"


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the Bosch Smart Home Camera integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
