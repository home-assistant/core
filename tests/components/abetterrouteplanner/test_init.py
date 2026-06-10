"""Tests for the A Better Routeplanner integration setup."""

from http import HTTPStatus
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
import pytest
from yarl import URL

from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner.api import AbrpApiError, AbrpAuthError
from homeassistant.components.abetterrouteplanner.const import (
    CONF_VEHICLE_IDS,
    DOMAIN,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    ABRP_GET_TLM_URL,
    ABRP_VEHICLE_LIST_URL,
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    SENSOR_TEST_SUB,
    USER_SUB,
    build_catalog_response,
    build_garage_response,
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
    """Setup with a fresh token loads the entry; unload returns it to NOT_LOADED."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    runtime_data = config_entry.runtime_data
    assert isinstance(runtime_data, AbrpData)
    assert isinstance(runtime_data.session, OAuth2Session)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


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
    """A 4xx from the token endpoint surfaces as SETUP_ERROR + reauth flow."""
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, status=HTTPStatus.UNAUTHORIZED)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id


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


@pytest.mark.usefixtures("current_request_with_host", "mock_sse_client")
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
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response())
    aioclient_mock.get(ABRP_VEHICLE_LIST_URL, json=build_catalog_response())

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
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("current_request_with_host", "mock_abrp_client")
async def test_reauth_end_to_end(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """End-to-end reauth: real async_setup_entry runs on reload after reauth."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": build_id_token(USER_SUB),
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["token"]["access_token"] == "updated-access-token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow_stale_token_refresh_unauthorized(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """End-to-end failure path: a freshly-minted token is already expired.

    The initial ``authorization_code`` token exchange succeeds but returns
    ``expires_in: -1`` so the access token is immediately stale. During
    ``async_setup_entry`` the OAuth2 session refreshes the token, and that
    refresh POST returns 401. The entry must end up in ``SETUP_ERROR`` and a
    reauth flow for the entry must be in progress.
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
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response())
    aioclient_mock.get(ABRP_VEHICLE_LIST_URL, json=build_catalog_response())

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

    # Three POSTs went out: the initial token exchange, the garage fetch for
    # the picker, and the refresh that 401'd during async_setup_entry.
    token_calls = [
        call for call in aioclient_mock.mock_calls if str(call[1]) == OAUTH2_TOKEN
    ]
    assert len(token_calls) == 2

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_first_refresh_auth_error_starts_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
) -> None:
    """A coordinator first-refresh ``AbrpAuthError`` triggers reauth.

    The OAuth session is valid (no token-refresh failure) but the v1 API
    rejects the access token (e.g. ABRP-side revocation). The integration
    must surface this as ``ConfigEntryAuthFailed`` so HA puts the entry in
    ``SETUP_ERROR`` and starts a reauth flow.
    """
    config_entry.add_to_hass(hass)
    mock_abrp_client.side_effect = AbrpAuthError("invalid session")

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id


async def test_first_refresh_api_error_setup_retry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
) -> None:
    """A coordinator first-refresh ``AbrpApiError`` surfaces as ``SETUP_RETRY``.

    Transient API/transport failures should not consume the user's reauth
    quota; the integration retries on HA's standard backoff instead.
    """
    config_entry.add_to_hass(hass)
    mock_abrp_client.side_effect = AbrpApiError("backend overloaded")

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


# SSE consumer task tests -----------------------------------------------------


async def test_sse_task_starts_on_setup(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_sse_client: MagicMock,
) -> None:
    """The SSE consumer is registered as an entry-scoped background task.

    ``stream(...)`` being called proves the task launched and entered its
    first connect attempt. The task itself is owned by the entry so
    ``ConfigEntry._background_tasks`` carries an active handle until
    unload.
    """
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert mock_sse_client.called
    background_tasks = getattr(config_entry_with_vehicles, "_background_tasks", set())
    assert any(not task.done() for task in background_tasks)


async def test_sse_task_cancelled_on_unload(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_sse_client: MagicMock,
) -> None:
    """Unloading the entry cancels the SSE consumer task cleanly.

    All background tasks tracked on the entry must finish (cancelled or
    completed) before unload returns; a hanging task would block HA
    shutdown.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    tasks_at_setup = list(
        getattr(config_entry_with_vehicles, "_background_tasks", set())
    )
    assert tasks_at_setup

    assert await hass.config_entries.async_unload(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    for task in tasks_at_setup:
        assert task.done()


async def test_async_setup_entry_seeds_telemetry_for_each_selected_vehicle(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    mock_sse_client: MagicMock,
    mock_seed_responses: AsyncMock,
) -> None:
    """``async_setup_entry`` seeds telemetry once per vehicle, AFTER garage refresh, BEFORE SSE spawn.

    Between garage first-refresh and platform forward, the integration calls
    ``async_seed_from_json_poll(selected_ids, token)`` so
    the sensor platform sees a populated ``telemetry_coordinator.data`` and
    can compute the per-metric visibility default deterministically.

    Order matters two ways:

    * **AFTER garage first-refresh** — the seed needs the selected
      ``vehicle_ids`` filtered against the live garage so we don't poll for
      a vehicle the user just removed from ABRP (the endpoint 401s on
      not-owned vehicles).
    * **BEFORE SSE task spawn** — so the SSE consumer doesn't race the
      seed and clobber a fresh frame with an older one-shot poll. The
      ordering is also what the sensor platform relies on for its visible-
      default decision at registration time.

    The 2-vehicle config_entry + set-equality oracle pins that EVERY
    selected vehicle is seeded (no silent drops, no deduplication
    regression).

    Three assertions: (a) seed was called for EACH selected vehicle id
    (set equality, not membership), (b) garage's ``async_get_vehicles``
    was called before the seed, (c) SSE ``stream`` was called after the
    seed.
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

    # Attach a parent MagicMock to capture interleaved call order across the
    # three boundary mocks (garage / seed / SSE). ``parent.mock_calls`` then
    # records each child call with its child name so we can assert ordering
    # without disturbing each mock's existing side_effect (the conftest
    # fixtures configure those carefully and overriding would break them).
    parent = MagicMock()
    parent.attach_mock(mock_abrp_client, "garage")
    parent.attach_mock(mock_seed_responses, "seed")
    parent.attach_mock(mock_sse_client, "sse")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    seeded_vehicle_ids = {call.args[0] for call in mock_seed_responses.call_args_list}
    assert seeded_vehicle_ids == {MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2}

    call_names = [call[0].split(".", 1)[0] for call in parent.mock_calls]
    assert "garage" in call_names, f"garage refresh not observed; calls={call_names}"
    assert "seed" in call_names, f"seed not observed; calls={call_names}"
    assert "sse" in call_names, f"SSE spawn not observed; calls={call_names}"
    assert call_names.index("garage") < call_names.index("seed"), (
        f"seed must run AFTER garage refresh; calls={call_names}"
    )
    assert call_names.index("seed") < call_names.index("sse"), (
        f"seed must run BEFORE SSE spawn; calls={call_names}"
    )


async def test_sse_auth_failure_starts_reauth(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_sse_client: MagicMock,
) -> None:
    """An ``AbrpAuthError`` from the SSE stream surfaces HA's reauth flow.

    The SSE consumer task can't fail entry setup (setup completed before
    it raised); instead the auth error reaches HA via the coordinator's
    ``async_set_update_error(ConfigEntryAuthFailed)`` path and starts the
    standard reauth flow for the entry.
    """
    mock_sse_client.side_effect = AbrpAuthError("invalid session")
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry_with_vehicles.entry_id
