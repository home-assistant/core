"""Tests for the A Better Routeplanner integration setup."""

from http import HTTPStatus
import logging
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from aioabrp import AbrpApiError, AbrpAuthError, Telemetry
from aiohttp import ClientError
import pytest
from yarl import URL

from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner.const import (
    CONF_VEHICLE_IDS,
    DOMAIN,
    OAUTH2_TOKEN,
)
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
    SENSOR_TEST_SUB,
    USER_SUB,
    build_id_token,
    complete_oauth_callback,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant) -> None:
    """Register the integration's OAuth2 implementation via async_setup.

    Also set up the ``auth`` component so the ``/auth/external/callback``
    endpoint and ``hass.http`` are available for tests that drive the full
    OAuth callback chain.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})


@pytest.mark.usefixtures("mock_abrp_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Setup with a fresh token loads the entry; unload returns it to NOT_LOADED.

    The default ``config_entry`` selects no vehicles, so no telemetry stream is
    spawned and no ``fake_stream`` fixture is needed.
    """
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    runtime_data = config_entry.runtime_data
    assert isinstance(runtime_data, AbrpData)
    assert isinstance(runtime_data.session, OAuth2Session)
    # No vehicles selected → no stream constructed.
    assert runtime_data.stream is None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    unloaded_state: ConfigEntryState = config_entry.state
    assert unloaded_state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
@pytest.mark.usefixtures("mock_abrp_client")
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
    """A 4xx from the token endpoint surfaces as SETUP_ERROR (no reauth flow)."""
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
    """A 5xx or connection error surfaces as SETUP_RETRY."""
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
    """End-to-end: user config flow drives real async_setup_entry to LOADED.

    The picker's garage fetch and the setup-path garage refresh + seed are
    served by ``mock_abrp_client``; the SSE stream is faked by ``fake_stream``
    because the user selects a vehicle (non-empty ``CONF_VEHICLE_IDS``).
    """
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": [str(MOCK_VEHICLE_ID)]}
    )
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
    assert entry.data["vehicle_ids"] == [str(MOCK_VEHICLE_ID)]
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
    """End-to-end failure path: a freshly-minted token is already expired.

    The initial ``authorization_code`` token exchange succeeds but returns
    ``expires_in: -1`` so the access token is immediately stale. During
    ``async_setup_entry`` the OAuth2 session refreshes the token, and that
    refresh POST returns 401. The entry must end up in ``SETUP_ERROR`` with no
    reauth flow in progress.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    # Sequence two POSTs to the same token endpoint via ``side_effect``: the
    # first (authorization_code exchange) returns an already-expired token; the
    # second (refresh during setup) returns 401.
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": [str(MOCK_VEHICLE_ID)]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    assert entry.state is ConfigEntryState.SETUP_ERROR

    # Two POSTs went out to the token endpoint: the initial authorization_code
    # exchange, and the refresh that 401'd during async_setup_entry. The garage
    # is now served by the mocked AbrpClient, not the token endpoint.
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
    """A garage-fetch ``AbrpAuthError`` surfaces as ``SETUP_ERROR``.

    The OAuth session is valid (no token-refresh failure) but the ABRP API
    rejects the access token (e.g. ABRP-side revocation). The setup-time garage
    fetch's ``async_get_vehicles`` raises ``AbrpAuthError`` and the integration
    must surface this as ``ConfigEntryAuthFailed`` so HA puts the entry in
    ``SETUP_ERROR``.
    """
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
    """A garage-fetch ``AbrpApiError`` surfaces as ``SETUP_RETRY``.

    Transient API/transport failures should surface as a retry, not an
    auth-error state; the integration maps them to ``ConfigEntryNotReady`` so HA
    retries on its standard backoff instead.
    """
    config_entry.add_to_hass(hass)
    mock_abrp_client.side_effect = AbrpApiError("backend overloaded")

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_setup_succeeds_with_degraded_device_card(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A display endpoint that 404s for every typecode must not block setup.

    With no display fixtures the per-typecode fetch 404s, so each vehicle's
    display degrades to ``None`` and the device card falls back to the raw
    typecode (manufacturer unset). Setup must still reach ``LOADED`` — a
    flaky/absent catalog endpoint degrades gracefully rather than failing setup
    into a retry loop — and a one-time ``INFO`` line flags the degraded card.
    """
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
async def test_stream_spawned_with_filtered_vehicle_ids(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """Setup spawns the telemetry stream for the selected ∩ present vehicles.

    Only ``MOCK_VEHICLE_ID`` is selected (out of the 2-vehicle garage), so the
    stream is constructed with exactly that id, started, and named after the
    entry title. The runtime data carries the live stream handle.
    """
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.LOADED

    stream = fake_stream.stream
    assert stream is not None
    assert stream.vehicle_ids == [MOCK_VEHICLE_ID]
    assert stream.started is True
    assert stream.name == config_entry_with_vehicles.title

    runtime_data = config_entry_with_vehicles.runtime_data
    assert isinstance(runtime_data, AbrpData)
    assert runtime_data.stream is stream


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_vehicle_ids_filtered_against_garage(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    fake_stream: Any,
) -> None:
    """A selected vehicle absent from the live garage is dropped from the stream.

    The entry selects ``MOCK_VEHICLE_ID`` plus a bogus id that the garage poll
    never returns; the stream is constructed with only the present id, proving
    the ``selected ∩ present`` filter is applied before spawning the stream.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), "999999999999"],
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    stream = fake_stream.stream
    assert stream is not None
    assert stream.vehicle_ids == [MOCK_VEHICLE_ID]


@pytest.mark.usefixtures("mock_abrp_client")
async def test_no_stream_when_no_vehicles_selected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """An entry with an empty selection spawns NO telemetry stream.

    ``config_entry`` selects no vehicles. Even with ``fake_stream`` patched in,
    the integration must skip stream construction entirely and leave
    ``runtime_data.stream`` as ``None``.
    """
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
    """Unloading an entry with a live stream stops it before unloading platforms."""
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
async def test_seed_runs_for_each_vehicle_before_stream_spawn(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """``async_setup_entry`` seeds telemetry once per selected vehicle, before the stream.

    Between garage first-refresh and the stream spawn, the integration seeds
    the telemetry coordinator via ``AbrpClient.async_get_current_telemetry``
    for every selected ∩ present vehicle so the sensor platform sees a
    populated snapshot. The 2-vehicle selection pins that EVERY selected
    vehicle is seeded (set equality, not membership), and that the stream is
    constructed afterwards with the same id set.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )
    entry.add_to_hass(hass)

    # Record which vehicle ids the seed path polls. Patch the bound function
    # directly (no autospec — the conftest already patched this attribute, and
    # autospec cannot spec an existing mock). Because the patch is not
    # autospecced, the class-attribute mock is not bound on access, so the
    # integration's ``client.async_get_current_telemetry(vid)`` call lands as
    # ``mock(vid)`` — the vehicle id is the sole positional arg.
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

    # Stream spawned after seeding, with the same (filtered) selection.
    stream = fake_stream.stream
    assert stream is not None
    assert set(stream.vehicle_ids) == {MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2}
    assert stream.started is True
