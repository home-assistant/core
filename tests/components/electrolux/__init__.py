"""Tests for the electrolux integration."""

from functools import cache

from electrolux_group_developer_sdk.client.dto.appliance import Appliance
from electrolux_group_developer_sdk.client.dto.appliance_details import ApplianceDetails
from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState

from homeassistant.components.electrolux.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

APPLIANCE_FIXTURES = ["fenix_oven", "pux_oven"]


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up Electrolux integration for tests."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@cache
def get_fixture_name(appliance_id: str) -> str:
    """Get the fixture name for the given appliance ID."""
    for name in APPLIANCE_FIXTURES:
        if load_appliance(name).applianceId == appliance_id:
            return name

    raise KeyError(f"Fixture name for appliance ID {appliance_id} does not exist")


def load_appliance(appliance_name: str) -> Appliance:
    """Load an Appliance object from a fixture for the given appliance name."""
    json_string = load_fixture(f"appliances/{appliance_name}.json", DOMAIN)
    return Appliance.model_validate_json(json_string)


def load_appliance_details(appliance_name: str) -> ApplianceDetails:
    """Load an ApplianceDetails object from a fixture for the given appliance name."""
    json_string = load_fixture(f"appliance_details/{appliance_name}.json", DOMAIN)
    return ApplianceDetails.model_validate_json(json_string)


def load_appliance_state(appliance_name: str) -> ApplianceState:
    """Load an ApplianceState object from a fixture for the given appliance name."""
    json_string = load_fixture(f"appliance_states/{appliance_name}.json", DOMAIN)
    return ApplianceState.model_validate_json(json_string)
