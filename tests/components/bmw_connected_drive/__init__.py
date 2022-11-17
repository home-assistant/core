"""Tests for the for the BMW Connected Drive integration."""

import json
from pathlib import Path

from bimmer_connected.account import MyBMWAccount
from bimmer_connected.api.utils import log_to_to_file

from homeassistant import config_entries
from homeassistant.components.bmw_connected_drive.const import (
    CONF_READ_ONLY,
    CONF_REFRESH_TOKEN,
    DOMAIN as BMW_DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, get_fixture_path, load_fixture

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "user@domain.com",
    CONF_PASSWORD: "p4ssw0rd",
    CONF_REGION: "rest_of_world",
}
FIXTURE_REFRESH_TOKEN = "SOME_REFRESH_TOKEN"

FIXTURE_CONFIG_ENTRY = {
    "entry_id": "1",
    "domain": BMW_DOMAIN,
    "title": FIXTURE_USER_INPUT[CONF_USERNAME],
    "data": {
        CONF_USERNAME: FIXTURE_USER_INPUT[CONF_USERNAME],
        CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD],
        CONF_REGION: FIXTURE_USER_INPUT[CONF_REGION],
        CONF_REFRESH_TOKEN: FIXTURE_REFRESH_TOKEN,
    },
    "options": {CONF_READ_ONLY: False},
    "source": config_entries.SOURCE_USER,
    "unique_id": f"{FIXTURE_USER_INPUT[CONF_REGION]}-{FIXTURE_USER_INPUT[CONF_REGION]}",
}


async def mock_vehicles_from_fixture(account: MyBMWAccount) -> None:
    """Load MyBMWVehicle from fixtures and add them to the account."""

    fixture_path = Path(get_fixture_path("", integration=BMW_DOMAIN))

    fixture_vehicles_bmw = list(fixture_path.rglob("vehicles_v2_bmw_*.json"))
    fixture_vehicles_mini = list(fixture_path.rglob("vehicles_v2_mini_*.json"))

    # Load vehicle base lists as provided by vehicles/v2 API
    vehicles = {
        "bmw": [
            vehicle
            for bmw_file in fixture_vehicles_bmw
            for vehicle in json.loads(load_fixture(bmw_file, integration=BMW_DOMAIN))
        ],
        "mini": [
            vehicle
            for mini_file in fixture_vehicles_mini
            for vehicle in json.loads(load_fixture(mini_file, integration=BMW_DOMAIN))
        ],
    }
    fetched_at = utcnow()

    # simulate storing fingerprints
    if account.config.log_response_path:
        for brand in ["bmw", "mini"]:
            log_to_to_file(
                json.dumps(vehicles[brand]),
                account.config.log_response_path,
                f"vehicles_v2_{brand}",
            )

    # Create a vehicle with base + specific state as provided by state/VIN API
    for vehicle_base in [vehicle for brand in vehicles.values() for vehicle in brand]:
        vehicle_state_path = (
            Path("vehicles")
            / vehicle_base["attributes"]["bodyType"]
            / f"state_{vehicle_base['vin']}_0.json"
        )
        vehicle_state = json.loads(
            load_fixture(
                vehicle_state_path,
                integration=BMW_DOMAIN,
            )
        )

        account.add_vehicle(
            vehicle_base,
            vehicle_state,
            fetched_at,
        )

        # simulate storing fingerprints
        if account.config.log_response_path:
            log_to_to_file(
                json.dumps(vehicle_state),
                account.config.log_response_path,
                f"state_{vehicle_base['vin']}",
            )


async def setup_mocked_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a fully setup config entry and all components based on fixtures."""

    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
