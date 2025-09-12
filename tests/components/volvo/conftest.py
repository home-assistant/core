"""Define fixtures for Volvo unit tests."""

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.auth import TOKEN_URL
from volvocarsapi.models import (
    VolvoCarsAvailableCommand,
    VolvoCarsLocation,
    VolvoCarsValueField,
    VolvoCarsValueStatusField,
    VolvoCarsVehicle,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.volvo.api import VolvoAuth
from homeassistant.components.volvo.const import CONF_VIN, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from . import async_load_fixture_as_json, async_load_fixture_as_value_field
from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    DEFAULT_API_KEY,
    DEFAULT_MODEL,
    DEFAULT_VIN,
    MOCK_ACCESS_TOKEN,
    SERVER_TOKEN_RESPONSE,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@dataclass
class MockApiData:
    """Container for mock API data."""

    vehicle: VolvoCarsVehicle
    commands: list[VolvoCarsAvailableCommand]
    location: dict[str, VolvoCarsLocation]
    availability: dict[str, VolvoCarsValueField]
    brakes: dict[str, VolvoCarsValueField]
    diagnostics: dict[str, VolvoCarsValueField]
    doors: dict[str, VolvoCarsValueField]
    energy_capabilities: JsonObjectType
    energy_state: dict[str, VolvoCarsValueStatusField]
    engine_status: dict[str, VolvoCarsValueField]
    engine_warnings: dict[str, VolvoCarsValueField]
    fuel_status: dict[str, VolvoCarsValueField]
    odometer: dict[str, VolvoCarsValueField]
    recharge_status: dict[str, VolvoCarsValueField]
    statistics: dict[str, VolvoCarsValueField]
    tyres: dict[str, VolvoCarsValueField]
    warnings: dict[str, VolvoCarsValueField]
    windows: dict[str, VolvoCarsValueField]


@pytest.fixture(params=[DEFAULT_MODEL])
def full_model(request: pytest.FixtureRequest) -> str:
    """Define which model to use when running the test. Use as a decorator."""
    return request.param


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEFAULT_VIN,
        data={
            "auth_implementation": DOMAIN,
            CONF_API_KEY: DEFAULT_API_KEY,
            CONF_VIN: DEFAULT_VIN,
            CONF_TOKEN: {
                "access_token": MOCK_ACCESS_TOKEN,
                "refresh_token": "mock-refresh-token",
                "expires_at": 123456789,
            },
        },
    )

    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
async def mock_api(
    hass: HomeAssistant,
    full_model: str,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials,
) -> AsyncGenerator[VolvoCarsApi]:
    """Mock the Volvo API."""

    mock_api_data = await _async_load_mock_api_data(hass, full_model)

    implementation = await async_get_config_entry_implementation(
        hass, mock_config_entry
    )
    oauth_session = OAuth2Session(hass, mock_config_entry, implementation)
    auth = VolvoAuth(aioclient_mock, oauth_session)
    api = VolvoCarsApi(
        aioclient_mock,
        auth,
        mock_config_entry.data[CONF_API_KEY],
        mock_config_entry.data[CONF_VIN],
    )

    with patch(
        "homeassistant.components.volvo.VolvoCarsApi",
        return_value=api,
    ):
        api.async_get_brakes_status = AsyncMock(return_value=mock_api_data.brakes)
        api.async_get_command_accessibility = AsyncMock(
            return_value=mock_api_data.availability
        )
        api.async_get_commands.return_value = mock_api_data.commands
        api.async_get_diagnostics = AsyncMock(return_value=mock_api_data.diagnostics)
        api.async_get_doors_status = AsyncMock(return_value=mock_api_data.doors)
        api.async_get_energy_capabilities = AsyncMock(
            return_value=mock_api_data.energy_capabilities
        )
        api.async_get_energy_state = AsyncMock(return_value=mock_api_data.energy_state)
        api.async_get_engine_status = AsyncMock(
            return_value=mock_api_data.engine_status
        )
        api.async_get_engine_warnings = AsyncMock(
            return_value=mock_api_data.engine_warnings
        )
        api.async_get_fuel_status = AsyncMock(return_value=mock_api_data.fuel_status)
        api.async_get_location = AsyncMock(return_value=mock_api_data.location)
        api.async_get_odometer = AsyncMock(return_value=mock_api_data.odometer)
        api.async_get_recharge_status = AsyncMock(
            return_value=mock_api_data.recharge_status
        )
        api.async_get_statistics = AsyncMock(return_value=mock_api_data.statistics)
        api.async_get_tyre_states = AsyncMock(return_value=mock_api_data.tyres)
        api.async_get_vehicle_details = AsyncMock(return_value=mock_api_data.vehicle)
        api.async_get_warnings = AsyncMock(return_value=mock_api_data.warnings)
        api.async_get_window_states = AsyncMock(return_value=mock_api_data.windows)

        yield api


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""

    async def run() -> bool:
        aioclient_mock.post(
            TOKEN_URL,
            json=SERVER_TOKEN_RESPONSE,
        )

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        return result

    return run


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.volvo.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def _async_load_mock_api_data(
    hass: HomeAssistant, full_model: str
) -> MockApiData:
    """Load all mock API data from fixtures."""
    vehicle_data = await async_load_fixture_as_json(hass, "vehicle", full_model)
    vehicle = VolvoCarsVehicle.from_dict(vehicle_data)

    commands_data = (
        await async_load_fixture_as_json(hass, "commands", full_model)
    ).get("data")
    commands = [VolvoCarsAvailableCommand.from_dict(item) for item in commands_data]

    location_data = await async_load_fixture_as_json(hass, "location", full_model)
    location = {"location": VolvoCarsLocation.from_dict(location_data)}

    availability = await async_load_fixture_as_value_field(
        hass, "availability", full_model
    )
    brakes = await async_load_fixture_as_value_field(hass, "brakes", full_model)
    diagnostics = await async_load_fixture_as_value_field(
        hass, "diagnostics", full_model
    )
    doors = await async_load_fixture_as_value_field(hass, "doors", full_model)
    energy_capabilities = await async_load_fixture_as_json(
        hass, "energy_capabilities", full_model
    )
    energy_state_data = await async_load_fixture_as_json(
        hass, "energy_state", full_model
    )
    energy_state = {
        key: VolvoCarsValueStatusField.from_dict(value)
        for key, value in energy_state_data.items()
    }
    engine_status = await async_load_fixture_as_value_field(
        hass, "engine_status", full_model
    )
    engine_warnings = await async_load_fixture_as_value_field(
        hass, "engine_warnings", full_model
    )
    fuel_status = await async_load_fixture_as_value_field(
        hass, "fuel_status", full_model
    )
    odometer = await async_load_fixture_as_value_field(hass, "odometer", full_model)
    recharge_status = await async_load_fixture_as_value_field(
        hass, "recharge_status", full_model
    )
    statistics = await async_load_fixture_as_value_field(hass, "statistics", full_model)
    tyres = await async_load_fixture_as_value_field(hass, "tyres", full_model)
    warnings = await async_load_fixture_as_value_field(hass, "warnings", full_model)
    windows = await async_load_fixture_as_value_field(hass, "windows", full_model)

    return MockApiData(
        vehicle=vehicle,
        commands=commands,
        location=location,
        availability=availability,
        brakes=brakes,
        diagnostics=diagnostics,
        doors=doors,
        energy_capabilities=energy_capabilities,
        energy_state=energy_state,
        engine_status=engine_status,
        engine_warnings=engine_warnings,
        fuel_status=fuel_status,
        odometer=odometer,
        recharge_status=recharge_status,
        statistics=statistics,
        tyres=tyres,
        warnings=warnings,
        windows=windows,
    )
