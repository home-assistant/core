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


def mock_vehicles_from_fixture() -> list[MyBMWVehicle]:
    """Load MyBMWVehicles from fixtures."""
    fixture_path = Path(get_fixture_path("", integration=BMW_DOMAIN))
    fixture_vehicles_v2 = list(fixture_path.rglob("vehicles_v2_*.json"))

    vehicles: list[dict] = []

    # First, load vehicle basee data as provided by vehicles/v2 API
    for f in fixture_vehicles_v2:
        vehicles.extend(
            json.loads(
                load_fixture(f.relative_to(fixture_path), integration=BMW_DOMAIN)
            )
        )

    # Then, add vehicle specific state as provided by state/VIN API
    for vehicle in vehicles:
        vehicle.update(
            json.loads(
                load_fixture(
                    f"{vehicle['attributes']['bodyType']}/state_{vehicle['vin']}_0.json",
                    integration=BMW_DOMAIN,
                )
            )
        )

    return vehicles


async def setup_mock_component(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a fully setup config entry and all components based on fixtures."""

    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    def mock_get_vehicles(self: MyBMWAccount) -> None:
        curr_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

        # Creating vehicles is currently a bit of a workaround due to the way it is
        # implemented in the library. Once the library has an improved way of handling,
        # this can be updated as well.
        self.vehicles = [
            MyBMWVehicle(
                self,
                {
                    **v,
                    "is_metric": self.config.use_metric_units,
                    "fetched_at": curr_time,
                },
            )
            for v in mock_vehicles_from_fixture()
        ]

    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        side_effect=mock_get_vehicles,
        autospec=True,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
