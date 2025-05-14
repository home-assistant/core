"""Define fixtures for Volvo unit tests."""

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from unittest.mock import AsyncMock, Mock, patch

from _pytest.fixtures import SubRequest
import pytest
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.auth import AUTHORIZE_URL, TOKEN_URL
from volvocarsapi.models import (
    VolvoApiException,
    VolvoCarsAvailableCommand,
    VolvoCarsLocation,
    VolvoCarsValueField,
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

from .common import load_json_object_fixture
from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
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
    return marker.args[0] if marker is not None else "xc40_electric_2024"


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="YV1ABCDEFG1234567",
        data={
            "auth_implementation": DOMAIN,
            CONF_API_KEY: "abcdef0123456879abcdef",
            CONF_VIN: "YV1ABCDEFG1234567",
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
async def mock_api(full_model_from_marker: str) -> AsyncGenerator[AsyncMock]:
    """Mock the Volvo API."""
    model = full_model_from_marker

    with patch(
        "homeassistant.components.volvo.VolvoCarsApi",
        spec_set=VolvoCarsApi,
    ) as mock_api:
        vehicle_data = load_json_object_fixture("vehicle", model)
        vehicle = VolvoCarsVehicle.from_dict(vehicle_data)

        commands_data = load_json_object_fixture("commands", model).get("data")
        commands = [VolvoCarsAvailableCommand.from_dict(item) for item in commands_data]  # type: ignore[arg-type, union-attr]

        location_data = load_json_object_fixture("location", model)
        location = {"location": VolvoCarsLocation.from_dict(location_data)}

        availability = _get_json_as_value_field("availability", model)
        brakes = _get_json_as_value_field("brakes", model)
        diagnostics = _get_json_as_value_field("diagnostics", model)
        doors = _get_json_as_value_field("doors", model)
        engine_status = _get_json_as_value_field("engine_status", model)
        engine_warnings = _get_json_as_value_field("engine_warnings", model)
        fuel_status = _get_json_as_value_field("fuel_status", model)
        odometer = _get_json_as_value_field("odometer", model)
        recharge_status = _get_json_as_value_field("recharge_status", model)
        statistics = _get_json_as_value_field("statistics", model)
        tyres = _get_json_as_value_field("tyres", model)
        warnings = _get_json_as_value_field("warnings", model)
        windows = _get_json_as_value_field("windows", model)

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

        yield mock_api


@pytest.fixture
async def mock_api_failure(full_model_from_marker: str) -> AsyncGenerator[AsyncMock]:
    """Mock the Volvo API so that it raises an exception for all calls during coordinator update."""
    model = full_model_from_marker
    vehicle_data = load_json_object_fixture("vehicle", model)
    vehicle = VolvoCarsVehicle.from_dict(vehicle_data)

    with patch(
        "homeassistant.components.volvo.VolvoCarsApi",
        spec_set=VolvoCarsApi,
    ) as mock_api:
        api: VolvoCarsApi = mock_api.return_value

        api.async_get_vehicle_details = AsyncMock(return_value=vehicle)

        api.async_get_brakes_status = AsyncMock(side_effect=VolvoApiException())
        api.async_get_command_accessibility = AsyncMock(side_effect=VolvoApiException())
        api.async_get_commands = AsyncMock(side_effect=VolvoApiException())
        api.async_get_diagnostics = AsyncMock(side_effect=VolvoApiException())
        api.async_get_doors_status = AsyncMock(side_effect=VolvoApiException())
        api.async_get_engine_status = AsyncMock(side_effect=VolvoApiException())
        api.async_get_engine_warnings = AsyncMock(side_effect=VolvoApiException())
        api.async_get_fuel_status = AsyncMock(side_effect=VolvoApiException())
        api.async_get_location = AsyncMock(side_effect=VolvoApiException())
        api.async_get_odometer = AsyncMock(side_effect=VolvoApiException())
        api.async_get_recharge_status = AsyncMock(side_effect=VolvoApiException())
        api.async_get_statistics = AsyncMock(side_effect=VolvoApiException())
        api.async_get_tyre_states = AsyncMock(side_effect=VolvoApiException())
        api.async_get_warnings = AsyncMock(side_effect=VolvoApiException())
        api.async_get_window_states = AsyncMock(side_effect=VolvoApiException())

        yield mock_api


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


def _get_json_as_value_field(name: str, model: str) -> dict[str, VolvoCarsValueField]:
    data = load_json_object_fixture(name, model)
    return {key: VolvoCarsValueField.from_dict(value) for key, value in data.items()}
