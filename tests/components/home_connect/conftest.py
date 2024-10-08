"""Test fixtures for home_connect."""

from collections.abc import Awaitable, Callable, Generator
import time
from typing import Any
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from homeconnect.api import HomeConnectAppliance, HomeConnectError
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.home_connect import update_all_devices
from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture

MOCK_APPLIANCES_PROPERTIES = {
    x["name"]: x
    for x in load_json_object_fixture("home_connect/appliances.json")["data"][
        "homeappliances"
    ]
}

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"
FAKE_AUTH_IMPL = "conftest-imported-cred"

SERVER_ACCESS_TOKEN = {
    "refresh_token": "server-refresh-token",
    "access_token": "server-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


@pytest.fixture(name="token_expiration_time")
def mock_token_expiration_time() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 86400


@pytest.fixture(name="token_entry")
def mock_token_entry(token_expiration_time: float) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "refresh_token": FAKE_REFRESH_TOKEN,
        "access_token": FAKE_ACCESS_TOKEN,
        "type": "Bearer",
        "expires_at": token_expiration_time,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": token_entry,
        },
        minor_version=2,
    )


@pytest.fixture(name="config_entry_v1_1")
def mock_config_entry_v1_1(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": token_entry,
        },
        minor_version=1,
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        FAKE_AUTH_IMPL,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


async def bypass_throttle(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Add kwarg to disable throttle."""
    await update_all_devices(hass, config_entry, no_throttle=True)


@pytest.fixture(name="bypass_throttle")
def mock_bypass_throttle() -> Generator[None]:
    """Fixture to bypass the throttle decorator in __init__."""
    with patch(
        "homeassistant.components.home_connect.update_all_devices",
        side_effect=bypass_throttle,
    ):
        yield


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    platforms: list[Platform],
    config_entry: MockConfigEntry,
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run() -> bool:
        with patch("homeassistant.components.home_connect.PLATFORMS", platforms):
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
        return result

    return run


@pytest.fixture(name="get_appliances")
def mock_get_appliances() -> Generator[MagicMock]:
    """Mock ConfigEntryAuth parent (HomeAssistantAPI) method."""
    with patch(
        "homeassistant.components.home_connect.api.ConfigEntryAuth.get_appliances",
    ) as mock:
        yield mock


@pytest.fixture(name="appliance")
def mock_appliance(request: pytest.FixtureRequest) -> MagicMock:
    """Fixture to mock Appliance."""
    app = "Washer"
    if hasattr(request, "param") and request.param:
        app = request.param

    mock = MagicMock(
        autospec=HomeConnectAppliance,
        **MOCK_APPLIANCES_PROPERTIES.get(app),
    )
    mock.name = app
    type(mock).status = PropertyMock(return_value={})
    mock.get.return_value = {}
    mock.get_programs_available.return_value = []
    mock.get_status.return_value = {}
    mock.get_settings.return_value = {}

    return mock


@pytest.fixture(name="problematic_appliance")
def mock_problematic_appliance(request: pytest.FixtureRequest) -> Mock:
    """Fixture to mock a problematic Appliance."""
    app = "Washer"
    if hasattr(request, "param") and request.param:
        app = request.param

    mock = Mock(
        autospec=HomeConnectAppliance,
        **MOCK_APPLIANCES_PROPERTIES.get(app),
    )
    mock.name = app
    type(mock).status = PropertyMock(return_value={})
    mock.get_programs_active.side_effect = HomeConnectError
    mock.get_programs_available.side_effect = HomeConnectError
    mock.start_program.side_effect = HomeConnectError
    mock.stop_program.side_effect = HomeConnectError
    mock.get_status.side_effect = HomeConnectError
    mock.get_settings.side_effect = HomeConnectError
    mock.set_setting.side_effect = HomeConnectError

    return mock


def get_all_appliances():
    """Return a list of `HomeConnectAppliance` instances for all appliances."""

    appliances = {}

    data = load_json_object_fixture("home_connect/appliances.json").get("data")
    programs_active = load_json_object_fixture("home_connect/programs-active.json")
    programs_available = load_json_object_fixture(
        "home_connect/programs-available.json"
    )

    def listen_callback(mock, callback):
        callback["callback"](mock)

    for home_appliance in data["homeappliances"]:
        api_status = load_json_object_fixture("home_connect/status.json")
        api_settings = load_json_object_fixture("home_connect/settings.json")

        ha_id = home_appliance["haId"]
        ha_type = home_appliance["type"]

        appliance = MagicMock(spec=HomeConnectAppliance, **home_appliance)
        appliance.name = home_appliance["name"]
        appliance.listen_events.side_effect = (
            lambda app=appliance, **x: listen_callback(app, x)
        )
        appliance.get_programs_active.return_value = programs_active.get(
            ha_type, {}
        ).get("data", {})
        appliance.get_programs_available.return_value = [
            program["key"]
            for program in programs_available.get(ha_type, {})
            .get("data", {})
            .get("programs", [])
        ]
        appliance.get_status.return_value = HomeConnectAppliance.json2dict(
            api_status.get("data", {}).get("status", [])
        )
        appliance.get_settings.return_value = HomeConnectAppliance.json2dict(
            api_settings.get(ha_type, {}).get("data", {}).get("settings", [])
        )
        setattr(appliance, "status", {})
        appliance.status.update(appliance.get_status.return_value)
        appliance.status.update(appliance.get_settings.return_value)
        appliance.set_setting.side_effect = (
            lambda x, y, appliance=appliance: appliance.status.update({x: {"value": y}})
        )
        appliance.start_program.side_effect = (
            lambda x, appliance=appliance: appliance.status.update(
                {"BSH.Common.Root.ActiveProgram": {"value": x}}
            )
        )
        appliance.stop_program.side_effect = (
            lambda appliance=appliance: appliance.status.update(
                {"BSH.Common.Root.ActiveProgram": {}}
            )
        )

        appliances[ha_id] = appliance

    return list(appliances.values())
