"""Tests for the A Better Routeplanner integration setup."""

from http import HTTPStatus
import logging
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from aioabrp import AbrpApiError, AbrpAuthError, AbrpVehicle, Telemetry
from aiohttp import ClientError
import pytest
from yarl import URL

from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    USER_SUB,
    build_id_token,
    complete_oauth_callback,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant) -> None:
    """Register the integration's OAuth2 implementation via async_setup."""
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Setup with a fresh token loads the entry; unload returns it to NOT_LOADED."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    runtime_data = config_entry.runtime_data
    assert isinstance(runtime_data, AbrpData)
    assert isinstance(runtime_data.session, OAuth2Session)
    assert runtime_data.stream is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    unloaded_state: ConfigEntryState = config_entry.state
    assert unloaded_state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_setup_token_refresh_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An expired token is refreshed during setup."""
    config_entry.add_to_hass(hass)

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    runtime_data = config_entry.runtime_data
    assert isinstance(runtime_data, AbrpData)
    assert isinstance(runtime_data.session, OAuth2Session)
    assert config_entry.data["token"]["access_token"] == "updated-access-token"
    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_setup_token_refresh_auth_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A terminal 4xx from the token endpoint surfaces as SETUP_ERROR."""
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, status=HTTPStatus.UNAUTHORIZED)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        pytest.param(HTTPStatus.INTERNAL_SERVER_ERROR, None, id="server_error"),
        pytest.param(None, ClientError("boom"), id="client_error"),
        pytest.param(None, TimeoutError("boom"), id="timeout"),
    ],
)
@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_setup_token_refresh_transient_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus | None,
    exc: Exception | None,
) -> None:
    """A 5xx, connection error or timeout surfaces as SETUP_RETRY."""
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, status=status, exc=exc)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_missing_implementation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """A missing OAuth2 implementation surfaces as SETUP_RETRY."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.abetterrouteplanner.config_entry_oauth2_flow"
        ".async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    # Sanity check that the import path we patched still exists.
    assert hasattr(config_entry_oauth2_flow, "async_get_config_entry_implementation")


@pytest.mark.usefixtures("current_request_with_host", "mock_abrp_client", "fake_stream")
async def test_full_flow_end_to_end(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """End-to-end: user config flow drives real async_setup_entry to LOADED."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": build_id_token(USER_SUB),
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    assert entry.state is ConfigEntryState.LOADED
    runtime_data = entry.runtime_data
    assert isinstance(runtime_data, AbrpData)
    assert isinstance(runtime_data.session, OAuth2Session)
    assert entry.data["token"]["access_token"] == "mock-access-token"
    assert entry.unique_id == USER_SUB

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    unloaded_state: ConfigEntryState = entry.state
    assert unloaded_state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("current_request_with_host", "mock_abrp_client", "fake_stream")
async def test_full_flow_stale_token_refresh_unauthorized(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """End-to-end failure path: a freshly-minted token is already expired."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    # Two POSTs to one endpoint: expired token first, then a 401 on refresh.
    responses = iter(
        [
            AiohttpClientMockResponse(
                "post",
                URL(OAUTH2_TOKEN),
                status=HTTPStatus.OK,
                json={
                    "access_token": "stale-access-token",
                    "refresh_token": "stale-refresh-token",
                    "token_type": "Bearer",
                    "expires_in": -1,
                    "id_token": build_id_token(USER_SUB),
                },
            ),
            AiohttpClientMockResponse(
                "post",
                URL(OAUTH2_TOKEN),
                status=HTTPStatus.UNAUTHORIZED,
            ),
        ]
    )

    async def _sequential_token_response(
        method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        return next(responses)

    aioclient_mock.post(OAUTH2_TOKEN, side_effect=_sequential_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    assert entry.state is ConfigEntryState.SETUP_ERROR

    # Only the token endpoint is counted; the garage is served by the mock.
    token_calls = [
        call for call in aioclient_mock.mock_calls if str(call[1]) == OAUTH2_TOKEN
    ]
    assert len(token_calls) == 2

    assert not hass.config_entries.flow.async_progress()


async def test_first_refresh_auth_error_setup_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
) -> None:
    """A garage-fetch ``AbrpAuthError`` surfaces as ``SETUP_ERROR``."""
    config_entry.add_to_hass(hass)
    mock_abrp_client.side_effect = AbrpAuthError("invalid session")

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not hass.config_entries.flow.async_progress()


async def test_first_refresh_api_error_setup_retry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
) -> None:
    """A garage-fetch ``AbrpApiError`` surfaces as ``SETUP_RETRY``."""
    config_entry.add_to_hass(hass)
    mock_abrp_client.side_effect = AbrpApiError("backend overloaded")

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_setup_succeeds_with_degraded_device(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A display endpoint that 404s for every typecode must not block setup."""
    config_entry_with_vehicles.add_to_hass(hass)

    with caplog.at_level(logging.INFO):
        assert await hass.config_entries.async_setup(
            config_entry_with_vehicles.entry_id
        )
        await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.LOADED

    scope = f"{config_entry_with_vehicles.unique_id}_{MOCK_VEHICLE_ID}"
    device = device_registry.async_get_device(identifiers={(DOMAIN, scope)})
    assert device is not None
    assert device.model == MOCK_VEHICLE_MODEL
    assert device.manufacturer is None

    assert any(
        record.levelno == logging.INFO
        and str(MOCK_VEHICLE_ID) in record.message
        and MOCK_VEHICLE_MODEL in record.message
        for record in caplog.records
    )


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_spawned_for_every_garage_vehicle(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """Setup spawns the telemetry stream covering the whole garage."""
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.LOADED

    stream = fake_stream.stream
    assert stream is not None
    assert stream.vehicle_ids == [MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2]
    assert stream.started is True
    assert stream.name == config_entry_with_vehicles.title

    runtime_data = config_entry_with_vehicles.runtime_data
    assert isinstance(runtime_data, AbrpData)
    assert runtime_data.stream is stream


async def test_no_stream_when_garage_is_empty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """An account whose garage is empty spawns NO telemetry stream."""
    mock_abrp_client.return_value = []
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert fake_stream.stream is None
    runtime_data = config_entry.runtime_data
    assert isinstance(runtime_data, AbrpData)
    assert runtime_data.stream is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_unload_stops_stream(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """Unloading an entry with a live stream stops it once the platforms unload."""
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    stream = fake_stream.stream
    assert stream is not None
    assert stream.stopped is False

    assert await hass.config_entries.async_unload(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.NOT_LOADED
    assert stream.stopped is True


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_stopped_when_platform_setup_raises(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """A platform setup failure must not leak the stream's background task.

    Home Assistant does not call ``async_unload_entry`` for an entry that never
    finished setting up, so the stop has to be registered as an on-unload hook.
    """
    config_entry_with_vehicles.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("platform setup blew up"),
    ):
        assert not await hass.config_entries.async_setup(
            config_entry_with_vehicles.entry_id
        )
        await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.SETUP_ERROR

    stream = fake_stream.stream
    assert stream is not None
    assert stream.started is True
    assert stream.stopped is True


@pytest.mark.parametrize(
    ("platforms_unloaded", "expected_state", "expected_stopped"),
    [
        pytest.param(True, ConfigEntryState.NOT_LOADED, True, id="platforms_unloaded"),
        pytest.param(
            False, ConfigEntryState.FAILED_UNLOAD, False, id="platforms_still_loaded"
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_survives_a_failed_platform_unload(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
    platforms_unloaded: bool,
    expected_state: ConfigEntryState,
    expected_stopped: bool,
) -> None:
    """The stream outlives an unload that left the entry's platforms loaded."""
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    stream = fake_stream.stream
    assert stream is not None
    assert stream.stopped is False

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=platforms_unloaded,
    ):
        unloaded = await hass.config_entries.async_unload(
            config_entry_with_vehicles.entry_id
        )
        await hass.async_block_till_done()

    assert unloaded is platforms_unloaded
    assert config_entry_with_vehicles.state is expected_state
    assert stream.stopped is expected_stopped


@pytest.mark.usefixtures("mock_abrp_client")
async def test_seed_runs_for_each_vehicle_before_stream_spawn(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Setup seeds telemetry once per garage vehicle, before the stream starts."""
    entry = config_entry_with_vehicles
    entry.add_to_hass(hass)

    # No autospec: conftest already patched this attribute, and an unbound
    # class-attribute mock receives the vehicle id as its sole positional arg.
    async def _record_seed(vehicle_id: int) -> Telemetry:
        return Telemetry()

    with patch(
        "aioabrp.AbrpClient.async_get_current_telemetry",
        side_effect=_record_seed,
    ) as mock_seed:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    seeded_vehicle_ids = {call.args[0] for call in mock_seed.call_args_list}
    assert seeded_vehicle_ids == {MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2}

    stream = fake_stream.stream
    assert stream is not None
    assert set(stream.vehicle_ids) == {MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2}
    assert stream.started is True


@pytest.mark.usefixtures("mock_abrp_client")
async def test_duplicate_garage_entry_yields_one_stream_id(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_abrp_vehicles: list[AbrpVehicle],
    fake_stream: Any,
) -> None:
    """A garage that repeats a vehicle subscribes that id only once."""
    mock_abrp_client.return_value = [*mock_abrp_vehicles, mock_abrp_vehicles[0]]
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert fake_stream.stream.vehicle_ids == [MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2]


@pytest.mark.usefixtures("mock_abrp_client")
async def test_vehicle_added_to_garage_appears_after_reload(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_abrp_vehicles: list[AbrpVehicle],
    device_registry: dr.DeviceRegistry,
    fake_stream: Any,
) -> None:
    """A vehicle added to the ABRP garage becomes a device on the next reload."""
    mock_abrp_client.return_value = mock_abrp_vehicles[:1]
    config_entry_with_vehicles.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    scope = config_entry_with_vehicles.unique_id
    identifiers = {(DOMAIN, f"{scope}_{MOCK_VEHICLE_ID_2}")}
    assert device_registry.async_get_device(identifiers=identifiers) is None

    mock_abrp_client.return_value = mock_abrp_vehicles
    await hass.config_entries.async_reload(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers=identifiers) is not None
    assert fake_stream.stream.vehicle_ids == [MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2]
