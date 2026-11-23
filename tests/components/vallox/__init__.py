"""Tests for the Vallox integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

TEST_HOST = "192.168.100.50"
TEST_NAME = "Vallox"

# Values for the metrics fixture, see conftest.py.
METRICS_UNIT_ON = {"A_CYC_MODE": 0}
METRICS_UNIT_OFF = {"A_CYC_MODE": 5}

# The fan shows the unit's profiles as preset modes. Home, Away and Auto are
# set in A_CYC_STATE. Boost, Fireplace and Extra are active as long as their
# timer runs.
METRICS_PROFILE_HOME = {"A_CYC_STATE": 0}
METRICS_PROFILE_AWAY = {"A_CYC_STATE": 1}
METRICS_PROFILE_AUTO = {"A_CYC_STATE": 2}
METRICS_PROFILE_UNKNOWN = {"A_CYC_STATE": 3}
METRICS_PROFILE_BOOST = {"A_CYC_BOOST_TIMER": 30}
METRICS_PROFILE_FIREPLACE = {"A_CYC_FIREPLACE_TIMER": 30}
METRICS_PROFILE_EXTRA = {"A_CYC_EXTRA_TIMER": 30}


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Vallox integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
