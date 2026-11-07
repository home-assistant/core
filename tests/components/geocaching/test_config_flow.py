"""Test the Geocaching config flow."""

import asyncio
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi.exceptions import GeocachingApiError, GeocachingInvalidSettingsError
from geocachingapi.models import GeocachingStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.geocaching import config_flow
from homeassistant.components.geocaching.const import (
    DOMAIN,
    ENVIRONMENT,
    ENVIRONMENT_URLS,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryState,
    ConfigSubentryDataWithId,
)
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import OAuth2TokenRequestConnectionError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from . import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

CURRENT_ENVIRONMENT_URLS = ENVIRONMENT_URLS[ENVIRONMENT]


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_geocaching_config_flow: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    assert result.get("type") is FlowResultType.EXTERNAL_STEP
    assert result.get("step_id") == "auth"
    assert result.get("url") == (
        f"{CURRENT_ENVIRONMENT_URLS['authorize_url']}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}&scope=*"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        CURRENT_ENVIRONMENT_URLS["token_url"],
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_existing_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_geocaching_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Check existing entry."""
    mock_config_entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        CURRENT_ENVIRONMENT_URLS["token_url"],
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    await hass.config_entries.flow.async_configure(result["flow_id"])
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_geocaching_config_flow: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Check if aborted when oauth error occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )
    assert result.get("type") is FlowResultType.EXTERNAL_STEP

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    # No user information is returned from API
    mock_geocaching_config_flow.update.return_value.user = None

    aioclient_mock.post(
        CURRENT_ENVIRONMENT_URLS["token_url"],
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "oauth_error"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_geocaching_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Geocaching reauthentication."""
    mock_config_entry.add_to_hass(hass)

    status = GeocachingStatus()
    status.user.username = "mock_user"
    status.user.reference_code = "PR12345"
    session = MagicMock()
    session.token = {"access_token": "mock-token"}

    with (
        patch(
            "homeassistant.components.geocaching.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.geocaching.OAuth2Session",
            return_value=session,
        ),
        patch(
            "homeassistant.components.geocaching.coordinator.GeocachingApi"
        ) as geocaching_api_mock,
    ):
        geocaching_api_mock.return_value.update = AsyncMock(return_value=status)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as async_schedule_reload:
        result = await mock_config_entry.start_reauth_flow(hass)

        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert "flow_id" in flows[0]

        result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

        state = config_entry_oauth2_flow._encode_jwt(
            hass,
            {
                "flow_id": result["flow_id"],
                "redirect_uri": "https://example.com/auth/external/callback",
            },
        )

        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == HTTPStatus.OK
        assert resp.headers["content-type"] == "text/html; charset=utf-8"

        aioclient_mock.post(
            CURRENT_ENVIRONMENT_URLS["token_url"],
            json={
                "access_token": "mock-access-token",
                "token_type": "bearer",
                "expires_in": 3599,
                "refresh_token": "mock-refresh_token",
            },
        )

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.data["token"]["access_token"] == "mock-access-token"
    async_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauthentication_reloads_unloaded_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_geocaching_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth reloads an entry whose initial setup never finished."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.geocaching.async_get_config_entry_implementation",
        side_effect=config_entry_oauth2_flow.ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED

    status = GeocachingStatus()
    status.user.username = "mock_user"
    status.user.reference_code = "PR12345"
    mock_geocaching_config_flow.update = AsyncMock(return_value=status)

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as async_schedule_reload:
        result = await mock_config_entry.start_reauth_flow(hass)

        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1

        result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

        state = config_entry_oauth2_flow._encode_jwt(
            hass,
            {
                "flow_id": result["flow_id"],
                "redirect_uri": "https://example.com/auth/external/callback",
            },
        )

        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == HTTPStatus.OK

        aioclient_mock.post(
            CURRENT_ENVIRONMENT_URLS["token_url"],
            json={
                "access_token": "mock-access-token",
                "token_type": "bearer",
                "expires_in": 3599,
                "refresh_token": "mock-refresh_token",
            },
        )

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data["token"]["access_token"] == "mock-access-token"
    async_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)


def _mock_loaded(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Add the config entry to hass in a loaded state with an OAuth session."""
    config_entry.add_to_hass(hass)
    config_entry.mock_state(hass, ConfigEntryState.LOADED)
    config_entry.runtime_data = MagicMock()
    config_entry.runtime_data.session.async_ensure_token_valid = AsyncMock()
    config_entry.runtime_data.session.token = {"access_token": "mock-access-token"}


async def test_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_geocaching_config_flow: MagicMock,
) -> None:
    """Test adding and normalizing a tracked cache subentry."""
    _mock_loaded(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "  gc12345  "}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_config_entry.subentries) == 1
    subentry = next(iter(mock_config_entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_TRACKED_CACHE
    assert subentry.title == "GC12345"
    assert subentry.unique_id == "GC12345"
    assert subentry.data == {CONF_CODE: "GC12345"}
    geocaching_api = config_flow.GeocachingApi
    assert geocaching_api.call_args.kwargs["token"] == "mock-access-token"
    assert geocaching_api.call_args.kwargs["settings"].tracked_cache_codes == {
        "GC12345"
    }
    mock_config_entry.runtime_data.session.async_ensure_token_valid.assert_awaited_once()
    mock_geocaching_config_flow.verify_settings.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "errors"),
    [
        pytest.param(
            GeocachingInvalidSettingsError("geocache", {"GC12345"}),
            {CONF_CODE: "cache_not_found"},
            id="cache_not_found",
        ),
        pytest.param(
            GeocachingApiError(),
            {"base": "cannot_connect"},
            id="cannot_connect",
        ),
    ],
)
async def test_subentry_flow_verify_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_geocaching_config_flow: MagicMock,
    exception: Exception,
    errors: dict[str, str],
) -> None:
    """Test verification errors when adding a subentry and recovering."""
    _mock_loaded(hass, mock_config_entry)
    mock_geocaching_config_flow.verify_settings.side_effect = exception

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "GC12345"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    assert not mock_config_entry.subentries

    mock_geocaching_config_flow.verify_settings.side_effect = None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "GC12345"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_flow_token_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_geocaching_config_flow: MagicMock,
) -> None:
    """Test a token refresh error when adding a subentry and recovering."""
    _mock_loaded(hass, mock_config_entry)
    session = mock_config_entry.runtime_data.session
    session.async_ensure_token_valid.side_effect = OAuth2TokenRequestConnectionError(
        domain=DOMAIN
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "GC12345"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert not mock_config_entry.subentries
    mock_geocaching_config_flow.verify_settings.assert_not_awaited()

    session.async_ensure_token_valid.side_effect = None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "GC12345"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_flow_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when the config entry is not loaded."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_subentry_flow_invalid_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_geocaching_config_flow: MagicMock,
) -> None:
    """Test adding a subentry with an invalid code."""
    _mock_loaded(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "INVALID"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_CODE: "invalid_cache_code"}
    mock_geocaching_config_flow.verify_settings.assert_not_awaited()

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "GC12345"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_flow_already_configured(
    hass: HomeAssistant,
    mock_geocaching_config_flow: MagicMock,
) -> None:
    """Test adding an already configured subentry code."""
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_CODE: "GC12345"},
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title="GC12345",
                unique_id="GC12345",
                subentry_id="existing-subentry",
            )
        ],
    )
    _mock_loaded(hass, config_entry)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "gc12345"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_CODE: "already_configured"}
    mock_geocaching_config_flow.verify_settings.assert_not_awaited()

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CODE: "GC67890"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_flow_concurrent_duplicate_cache(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_geocaching_config_flow: MagicMock,
) -> None:
    """Test concurrent flows for the same cache create only one subentry."""
    _mock_loaded(hass, mock_config_entry)

    verification_started = asyncio.Event()
    verification_calls = 0

    async def wait_for_both_verifications() -> None:
        nonlocal verification_calls
        verification_calls += 1
        if verification_calls == 2:
            verification_started.set()
        await verification_started.wait()

    mock_geocaching_config_flow.verify_settings.side_effect = (
        wait_for_both_verifications
    )

    flow_results = [
        await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
            context={"source": SOURCE_USER},
        )
        for _ in range(2)
    ]
    results = await asyncio.gather(
        *(
            hass.config_entries.subentries.async_configure(
                flow_result["flow_id"], {CONF_CODE: "GC12345"}
            )
            for flow_result in flow_results
        )
    )

    subentries = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_TRACKED_CACHE)
    assert len(subentries) == 1
    assert [result["type"] for result in results].count(
        FlowResultType.CREATE_ENTRY
    ) == 1
    abort_result = next(
        result for result in results if result["type"] is FlowResultType.ABORT
    )
    assert abort_result["reason"] == "already_configured"


async def test_subentry_flow_maximum(
    hass: HomeAssistant,
) -> None:
    """Test aborting when the maximum number of subentries is configured."""
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_CODE: f"GC{number}"},
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title=f"GC{number}",
                unique_id=f"GC{number}",
                subentry_id=f"subentry-{number}",
            )
            for number in range(50)
        ],
    )
    _mock_loaded(hass, config_entry)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "too_many_caches"


async def test_subentry_flow_maximum_with_concurrent_additions(
    hass: HomeAssistant,
    mock_geocaching_config_flow: MagicMock,
) -> None:
    """Test concurrent subentry flows cannot exceed the cache limit."""
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_CODE: f"GC{number}"},
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title=f"GC{number}",
                unique_id=f"GC{number}",
                subentry_id=f"subentry-{number}",
            )
            for number in range(49)
        ],
    )
    _mock_loaded(hass, config_entry)

    verification_started = asyncio.Event()
    verification_calls = 0

    async def wait_for_both_verifications() -> None:
        nonlocal verification_calls
        verification_calls += 1
        if verification_calls == 2:
            verification_started.set()
        await verification_started.wait()

    mock_geocaching_config_flow.verify_settings.side_effect = (
        wait_for_both_verifications
    )

    flow_results = [
        await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
            context={"source": SOURCE_USER},
        )
        for _ in range(2)
    ]
    configure_tasks = [
        hass.config_entries.subentries.async_configure(
            flow_result["flow_id"], {CONF_CODE: f"GC{number}"}
        )
        for number, flow_result in enumerate(flow_results, start=50000)
    ]

    results = await asyncio.gather(*configure_tasks)

    assert len(config_entry.get_subentries_of_type(SUBENTRY_TYPE_TRACKED_CACHE)) == 50
    assert [result["type"] for result in results].count(
        FlowResultType.CREATE_ENTRY
    ) == 1
    abort_result = next(
        result for result in results if result["type"] is FlowResultType.ABORT
    )
    assert abort_result["reason"] == "too_many_caches"
