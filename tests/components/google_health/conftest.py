"""Test fixtures for Google Health."""

from collections.abc import Awaitable, Callable, Generator
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from google_health_api.model import (
    BODY_FAT,
    DAILY_RESTING_HEART_RATE,
    WEIGHT,
    ActiveEnergyBurnedRollupValue,
    DailyRollupDataPoint,
    DataPoint,
    DataType,
    DistanceRollupValue,
    FloorsRollupValue,
    Identity,
    ListDataPointResult,
    StepsRollupValue,
    TotalCaloriesRollupValue,
    UserInfo,
    _ListDataPointsModel,
)
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_health.const import DOMAIN, OAUTH_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"


def _rollup_fixture(
    filename: str, rollup_cls: type, field_name: str
) -> DailyRollupDataPoint | None:
    """Build the most recent daily rollup data point from a fixture."""
    points = load_json_object_fixture(filename, DOMAIN)["rollupDataPoints"]
    if not points:
        return None
    return DailyRollupDataPoint.from_api_dict(rollup_cls, field_name, points[0])


def _list_fixture(filename: str, data_type: DataType) -> ListDataPointResult:
    """Build a list data point result from a fixture."""
    data_points = [
        DataPoint.from_api_dict(data_type, item)
        for item in load_json_object_fixture(filename, DOMAIN)["dataPoints"]
    ]
    return ListDataPointResult(_ListDataPointsModel(data_points=data_points))


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return int(time.time() + 86400)


@pytest.fixture
def scopes() -> list[str]:
    """Fixture with scopes to set up."""
    return OAUTH_SCOPES


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: int, scopes: list[str]) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_ACCESS_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(scopes),
        "token_type": "Bearer",
        "expires_at": expires_at,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Google Health",
        unique_id="mock-health-user-id",
        entry_id="01J0BC4QM2YBRP6H5G933CETT7",
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.google_health.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_google_health_client() -> Generator[AsyncMock]:
    """Mock a Google Health client."""
    with (
        patch(
            "homeassistant.components.google_health.GoogleHealthApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.google_health.config_flow.GoogleHealthApi",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.steps = AsyncMock()
        client.steps.today.return_value = _rollup_fixture(
            "steps.json", StepsRollupValue, "steps"
        )
        client.steps.required_read_scopes = [
            "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly"
        ]
        client.distance = AsyncMock()
        client.distance.today.return_value = _rollup_fixture(
            "distance.json", DistanceRollupValue, "distance"
        )
        client.active_energy_burned = AsyncMock()
        client.active_energy_burned.today.return_value = _rollup_fixture(
            "active_energy_burned.json",
            ActiveEnergyBurnedRollupValue,
            "activeEnergyBurned",
        )
        client.total_calories = AsyncMock()
        client.total_calories.today.return_value = _rollup_fixture(
            "total_calories.json", TotalCaloriesRollupValue, "totalCalories"
        )
        client.floors = AsyncMock()
        client.floors.today.return_value = _rollup_fixture(
            "floors.json", FloorsRollupValue, "floors"
        )
        client.weight = AsyncMock()
        client.weight.list.return_value = _list_fixture("weight.json", WEIGHT)
        client.weight.required_read_scopes = [
            "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"
        ]
        client.daily_resting_heart_rate = AsyncMock()
        client.daily_resting_heart_rate.list.return_value = _list_fixture(
            "resting_heart_rate.json", DAILY_RESTING_HEART_RATE
        )
        client.body_fat = AsyncMock()
        client.body_fat.list.return_value = _list_fixture("body_fat.json", BODY_FAT)
        client.get_identity.return_value = Identity.from_dict(
            load_json_object_fixture("identity.json", DOMAIN)
        )
        client.get_user_info.return_value = UserInfo.from_dict(
            load_json_object_fixture("userinfo.json", DOMAIN)
        )
        yield client


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_credentials: None,
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run() -> bool:
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return result

    return run
