"""Tests for the for the BMW Connected Drive integration."""

from pathlib import Path

from bimmer_connected.api.authentication import MyBMWAuthentication
from bimmer_connected.const import (
    VEHICLE_CHARGING_DETAILS_URL,
    VEHICLE_STATE_URL,
    VEHICLES_URL,
)
import httpx
import respx

from homeassistant import config_entries
from homeassistant.components.bmw_connected_drive.const import (
    CONF_READ_ONLY,
    CONF_REFRESH_TOKEN,
    DOMAIN as BMW_DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    get_fixture_path,
    load_json_array_fixture,
    load_json_object_fixture,
)

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

FIXTURE_PATH = Path(get_fixture_path("", integration=BMW_DOMAIN))
FIXTURE_FILES = {
    "vehicles": sorted(FIXTURE_PATH.rglob("*-eadrax-vcs_v4_vehicles.json")),
    "states": {
        p.stem.split("_")[-1]: p
        for p in FIXTURE_PATH.rglob("*-eadrax-vcs_v4_vehicles_state_*.json")
    },
    "charging": {
        p.stem.split("_")[-1]: p
        for p in FIXTURE_PATH.rglob("*-eadrax-crccs_v2_vehicles_*.json")
    },
}


def vehicles_sideeffect(request: httpx.Request) -> httpx.Response:
    """Return /vehicles response based on x-user-agent."""
    x_user_agent = request.headers.get("x-user-agent", "").split(";")
    brand = x_user_agent[1]
    vehicles = []
    for vehicle_file in FIXTURE_FILES["vehicles"]:
        if vehicle_file.name.startswith(brand):
            vehicles.extend(
                load_json_array_fixture(vehicle_file, integration=BMW_DOMAIN)
            )
    return httpx.Response(200, json=vehicles)


def vehicle_state_sideeffect(request: httpx.Request) -> httpx.Response:
    """Return /vehicles/state response."""
    try:
        state_file = FIXTURE_FILES["states"][request.headers["bmw-vin"]]
        return httpx.Response(
            200, json=load_json_object_fixture(state_file, integration=BMW_DOMAIN)
        )
    except KeyError:
        return httpx.Response(404)


def vehicle_charging_sideeffect(request: httpx.Request) -> httpx.Response:
    """Return /vehicles/state response."""
    try:
        charging_file = FIXTURE_FILES["charging"][request.headers["bmw-vin"]]
        return httpx.Response(
            200, json=load_json_object_fixture(charging_file, integration=BMW_DOMAIN)
        )
    except KeyError:
        return httpx.Response(404)


def mock_vehicles() -> respx.Router:
    """Return mocked adapter for vehicles."""
    router = respx.mock(assert_all_called=False)

    # Get vehicle list
    router.get(VEHICLES_URL).mock(side_effect=vehicles_sideeffect)

    # Get vehicle state
    router.get(VEHICLE_STATE_URL).mock(side_effect=vehicle_state_sideeffect)

    # Get vehicle charging details
    router.get(VEHICLE_CHARGING_DETAILS_URL).mock(
        side_effect=vehicle_charging_sideeffect
    )
    return router


async def mock_login(auth: MyBMWAuthentication) -> None:
    """Mock a successful login."""
    auth.access_token = "SOME_ACCESS_TOKEN"


async def setup_mocked_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a fully setup config entry and all components based on fixtures."""

    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
