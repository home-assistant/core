"""Define fixtures for Volvo unit tests."""

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from unittest.mock import AsyncMock, Mock, patch

from _pytest.fixtures import SubRequest
import pytest
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.auth import AUTHORIZE_URL, TOKEN_URL
from volvocarsapi.models import (
    VolvoCarsAvailableCommand,
    VolvoCarsLocation,
    VolvoCarsVehicle,
)
from volvocarsapi.scopes import DEFAULT_SCOPES
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.volvo.const import CONF_VIN, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .common import async_load_fixture_as_json, async_load_fixture_as_value_field
from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    DEFAULT_MODEL,
    DEFAULT_VIN,
    MOCK_ACCESS_TOKEN,
    REDIRECT_URI,
    SERVER_TOKEN_RESPONSE,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


def pytest_configure(config: pytest.Config):
    """Configure pytest."""
    config.addinivalue_line("markers", "use_model(name): mark test to use given model")


def model(name: str):
    """Define which model to use when running the test. Use as a decorator."""
    return pytest.mark.use_model(name)


@pytest.fixture
def model_from_marker(full_model_from_marker: str) -> str:  # pylint: disable=hass-argument-type
    """Get model from marker."""
    return full_model_from_marker[: full_model_from_marker.index("_")]


@pytest.fixture
def full_model_from_marker(request: SubRequest) -> str:  # pylint: disable=hass-argument-type
    """Get full model from marker."""
    marker = request.node.get_closest_marker("use_model")
    return marker.args[0] if marker is not None else DEFAULT_MODEL


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEFAULT_VIN,
        data={
            "auth_implementation": DOMAIN,
            CONF_API_KEY: "abcdef0123456879abcdef",
            CONF_VIN: DEFAULT_VIN,
            CONF_TOKEN: {
                "access_token": MOCK_ACCESS_TOKEN,
                "refresh_token": "mock-refresh-token",
                "expires_at": 123456789,
            },
        },
    )

    config_entry.runtime_data = Mock()
    config_entry.add_to_hass(hass)

    return config_entry


@pytest.fixture(autouse=True)
async def mock_api(
    hass: HomeAssistant, full_model_from_marker: str
) -> AsyncGenerator[AsyncMock]:
    """Mock the Volvo API."""
    model = full_model_from_marker

    with patch(
        "homeassistant.components.volvo.VolvoCarsApi",
        spec_set=VolvoCarsApi,
    ) as mock_api:
        vehicle_data = await async_load_fixture_as_json(hass, "vehicle", model)
        vehicle = VolvoCarsVehicle.from_dict(vehicle_data)

        commands_data = (await async_load_fixture_as_json(hass, "commands", model)).get(
            "data"
        )
        commands = [VolvoCarsAvailableCommand.from_dict(item) for item in commands_data]

        location_data = await async_load_fixture_as_json(hass, "location", model)
        location = {"location": VolvoCarsLocation.from_dict(location_data)}

        availability = await async_load_fixture_as_value_field(
            hass, "availability", model
        )
        brakes = await async_load_fixture_as_value_field(hass, "brakes", model)
        diagnostics = await async_load_fixture_as_value_field(
            hass, "diagnostics", model
        )
        doors = await async_load_fixture_as_value_field(hass, "doors", model)
        engine_status = await async_load_fixture_as_value_field(
            hass, "engine_status", model
        )
        engine_warnings = await async_load_fixture_as_value_field(
            hass, "engine_warnings", model
        )
        fuel_status = await async_load_fixture_as_value_field(
            hass, "fuel_status", model
        )
        odometer = await async_load_fixture_as_value_field(hass, "odometer", model)
        recharge_status = await async_load_fixture_as_value_field(
            hass, "recharge_status", model
        )
        statistics = await async_load_fixture_as_value_field(hass, "statistics", model)
        tyres = await async_load_fixture_as_value_field(hass, "tyres", model)
        warnings = await async_load_fixture_as_value_field(hass, "warnings", model)
        windows = await async_load_fixture_as_value_field(hass, "windows", model)

        api: VolvoCarsApi = mock_api.return_value
        api.async_get_brakes_status = AsyncMock(return_value=brakes)
        api.async_get_command_accessibility = AsyncMock(return_value=availability)
        api.async_get_commands = AsyncMock(return_value=commands)
        api.async_get_diagnostics = AsyncMock(return_value=diagnostics)
        api.async_get_doors_status = AsyncMock(return_value=doors)
        api.async_get_engine_status = AsyncMock(return_value=engine_status)
        api.async_get_engine_warnings = AsyncMock(return_value=engine_warnings)
        api.async_get_fuel_status = AsyncMock(return_value=fuel_status)
        api.async_get_location = AsyncMock(return_value=location)
        api.async_get_odometer = AsyncMock(return_value=odometer)
        api.async_get_recharge_status = AsyncMock(return_value=recharge_status)
        api.async_get_statistics = AsyncMock(return_value=statistics)
        api.async_get_tyre_states = AsyncMock(return_value=tyres)
        api.async_get_vehicle_details = AsyncMock(return_value=vehicle)
        api.async_get_warnings = AsyncMock(return_value=warnings)
        api.async_get_window_states = AsyncMock(return_value=windows)

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
async def config_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> config_entries.ConfigFlowResult:
    """Initialize a new config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    result_url = URL(result["url"])
    assert f"{result_url.origin()}{result_url.path}" == AUTHORIZE_URL
    assert result_url.query["response_type"] == "code"
    assert result_url.query["client_id"] == CLIENT_ID
    assert result_url.query["redirect_uri"] == REDIRECT_URI
    assert result_url.query["state"] == state
    assert result_url.query["code_challenge"]
    assert result_url.query["code_challenge_method"] == "S256"
    assert result_url.query["scope"] == " ".join(DEFAULT_SCOPES)

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    return result


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
