"""Tests for the for the BMW Connected Drive integration."""

import datetime
import json
from pathlib import Path
from unittest.mock import patch

from bimmer_connected.account import MyBMWAccount
from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant import config_entries
from homeassistant.components.bmw_connected_drive.const import (
    CONF_READ_ONLY,
    DOMAIN as BMW_DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, get_fixture_path, load_fixture

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "user@domain.com",
    CONF_PASSWORD: "p4ssw0rd",
    CONF_REGION: "rest_of_world",
}

FIXTURE_CONFIG_ENTRY = {
    "entry_id": "1",
    "domain": BMW_DOMAIN,
    "title": FIXTURE_USER_INPUT[CONF_USERNAME],
    "data": {
        CONF_USERNAME: FIXTURE_USER_INPUT[CONF_USERNAME],
        CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD],
        CONF_REGION: FIXTURE_USER_INPUT[CONF_REGION],
    },
    "options": {CONF_READ_ONLY: False},
    "source": config_entries.SOURCE_USER,
    "unique_id": f"{FIXTURE_USER_INPUT[CONF_REGION]}-{FIXTURE_USER_INPUT[CONF_REGION]}",
}


def mock_get_vehicles_from_fixture(account: MyBMWAccount) -> None:
    """Load MyBMWVehicles from fixtures and add them to the account."""
    fixture_path = Path(get_fixture_path("", integration=BMW_DOMAIN))
    fixture_vehicles_v2 = list(fixture_path.rglob("vehicles_v2_*.json"))

    # Creating vehicles is currently a bit of a workaround due to the way it is
    # implemented in the library. Once the library has an improved way of handling,
    # this can be updated as well.

    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    vehicles: list[dict] = []

    # First, load vehicle basee data as provided by vehicles/v2 API
    for f in fixture_vehicles_v2:
        vehicles.extend(
            json.loads(
                load_fixture(f.relative_to(fixture_path), integration=BMW_DOMAIN)
            )
        )

    # Then, add vehicle specific state as provided by state/VIN API
    for vehicle_dict in vehicles:
        vehicle_dict.update(
            json.loads(
                load_fixture(
                    f"{vehicle_dict['attributes']['bodyType']}/state_{vehicle_dict['vin']}_0.json",
                    integration=BMW_DOMAIN,
                )
            )
        )
        # Add unit information
        vehicle_dict["is_metric"] = account.config.use_metric_units
        vehicle_dict["fetched_at"] = fetched_at

        # If vehicle already exists, just update it's state
        existing_vehicle = account.get_vehicle(vehicle_dict["vin"])
        if existing_vehicle:
            existing_vehicle.update_state(vehicle_dict)
        else:
            account.vehicles.append(MyBMWVehicle(account, vehicle_dict))


async def setup_mock_component(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a fully setup config entry and all components based on fixtures."""

    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        side_effect=mock_get_vehicles_from_fixture,
        autospec=True,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
