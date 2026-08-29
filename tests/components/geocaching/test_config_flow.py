"""Test the Geocaching config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi.models import GeocachingStatus, GeocachingTrackable
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.geocaching.const import (
    CONF_TRACKABLE_CODES,
    DOMAIN,
    ENVIRONMENT,
    ENVIRONMENT_URLS,
    MAX_TRACKED_TRACKABLES,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.components.geocaching.sensor import PROFILE_SENSORS
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryDataWithId
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

from . import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CURRENT_ENVIRONMENT_URLS = ENVIRONMENT_URLS[ENVIRONMENT]


def _create_status(
    account_reference_code: str, *trackable_codes: str
) -> GeocachingStatus:
    """Create API status data for an account and its trackables."""
    status = GeocachingStatus()
    status.user.username = account_reference_code
    status.user.reference_code = account_reference_code
    status.trackables = {
        code: GeocachingTrackable(reference_code=code, name=code)
        for code in trackable_codes
    }
    return status


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
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as async_reload:
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
    async_reload.assert_awaited_once_with(mock_config_entry.entry_id)


async def test_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding and normalizing a tracked cache subentry."""
    mock_config_entry.add_to_hass(hass)

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


async def test_subentry_flow_invalid_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding a subentry with an invalid code."""
    mock_config_entry.add_to_hass(hass)

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


async def test_subentry_flow_already_configured(
    hass: HomeAssistant,
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
    config_entry.add_to_hass(hass)

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
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_TRACKED_CACHE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "too_many_caches"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuring tracked trackables reloads a loaded entry."""
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
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as async_reload:
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_TRACKABLE_CODES: "TB12345, tb67890\nTB12345"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_TRACKABLE_CODES: ["TB12345", "TB67890"]}
    assert mock_config_entry.options == {CONF_TRACKABLE_CODES: ["TB12345", "TB67890"]}
    async_reload.assert_awaited_once_with(mock_config_entry.entry_id)


async def test_options_flow_removes_trackable_registry_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a trackable cleans its entities and device before reload."""
    removed_code = "TB12345"
    retained_code = "TB67890"
    account_reference_code = "PR12345"
    config_entry = MockConfigEntry(
        title="Account",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        options={CONF_TRACKABLE_CODES: [" tb12345 ", retained_code]},
        unique_id="mock_user",
    )
    config_entry.add_to_hass(hass)

    initial_status = _create_status(account_reference_code, removed_code, retained_code)
    reloaded_status = _create_status(account_reference_code, retained_code)
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
        geocaching_api_mock.return_value.update = AsyncMock(
            side_effect=[initial_status, reloaded_status]
        )
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        removed_unique_id = (
            f"{account_reference_code}_{removed_code}_kilometers_traveled"
        )
        removed_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, removed_unique_id
        )
        assert removed_entity_id is not None
        removed_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{account_reference_code}_{removed_code}"),
            config_entry.entry_id,
        )
        assert removed_device is not None
        disabled_entity = entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{removed_unique_id}_disabled",
            config_entry=config_entry,
            device_id=removed_device.id,
            disabled_by=er.RegistryEntryDisabler.USER,
        )

        retained_unique_id = (
            f"{account_reference_code}_{retained_code}_kilometers_traveled"
        )
        retained_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, retained_unique_id
        )
        assert retained_entity_id is not None

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_TRACKABLE_CODES: retained_code},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_TRACKABLE_CODES: [retained_code]}
    assert hass.states.get(removed_entity_id) is None
    assert entity_registry.async_get(removed_entity_id) is None
    assert entity_registry.async_get(disabled_entity.entity_id) is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{account_reference_code}_{removed_code}"),
            config_entry.entry_id,
        )
        is None
    )

    assert hass.states.get(retained_entity_id) is not None
    retained_entity = entity_registry.async_get(retained_entity_id)
    assert retained_entity is not None
    assert retained_entity.config_entry_id == config_entry.entry_id
    assert retained_entity.config_subentry_id is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{account_reference_code}_{retained_code}"),
            config_entry.entry_id,
        )
        is not None
    )

    for description in PROFILE_SENSORS:
        profile_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{account_reference_code}_{description.key}"
        )
        assert profile_entity_id is not None
        assert hass.states.get(profile_entity_id) is not None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, account_reference_code), config_entry.entry_id
        )
        is not None
    )


async def test_options_flow_removes_trackable_from_unloaded_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test registry cleanup for an unloaded entry is scoped to that entry."""
    trackable_code = "TB12345"
    entries: list[tuple[MockConfigEntry, str]] = []

    for account_reference_code, entry_id in (
        ("PR11111", "entry-one"),
        ("PR22222", "entry-two"),
    ):
        config_entry = MockConfigEntry(
            title=account_reference_code,
            domain=DOMAIN,
            data={"id": entry_id, "auth_implementation": DOMAIN},
            options={CONF_TRACKABLE_CODES: [trackable_code]},
            entry_id=entry_id,
            unique_id=entry_id,
        )
        config_entry.add_to_hass(hass)
        status = _create_status(account_reference_code, trackable_code)
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
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
        entries.append((config_entry, account_reference_code))

    removed_entry, removed_account = entries[0]
    retained_entry, retained_account = entries[1]
    removed_unique_id = f"{removed_account}_{trackable_code}_kilometers_traveled"
    removed_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, removed_unique_id
    )
    assert removed_entity_id is not None
    removed_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{removed_account}_{trackable_code}"), removed_entry.entry_id
    )
    assert removed_device is not None

    assert await hass.config_entries.async_unload(removed_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(removed_entity_id) is not None
    assert device_registry.async_get(removed_device.id) is not None

    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as async_reload:
        result = await hass.config_entries.options.async_init(removed_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_TRACKABLE_CODES: ""}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert removed_entry.options == {CONF_TRACKABLE_CODES: []}
    assert entity_registry.async_get(removed_entity_id) is None
    assert device_registry.async_get(removed_device.id) is None
    async_reload.assert_not_awaited()

    retained_unique_id = f"{retained_account}_{trackable_code}_kilometers_traveled"
    retained_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, retained_unique_id
    )
    assert retained_entity_id is not None
    retained_entity = entity_registry.async_get(retained_entity_id)
    assert retained_entity is not None
    assert retained_entity.config_entry_id == retained_entry.entry_id
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{retained_account}_{trackable_code}"),
            retained_entry.entry_id,
        )
        is not None
    )


async def test_options_flow_maximum_trackables(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuring the maximum number of tracked trackables."""
    mock_config_entry.add_to_hass(hass)
    trackable_codes = [f"TB{number}" for number in range(MAX_TRACKED_TRACKABLES)]

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_TRACKABLE_CODES: "\n".join(trackable_codes)},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_TRACKABLE_CODES: trackable_codes}


@pytest.mark.parametrize(
    ("trackable_codes", "error"),
    [
        pytest.param("INVALID", "invalid_trackable_code", id="invalid"),
        pytest.param(
            "\n".join(f"TB{number}" for number in range(MAX_TRACKED_TRACKABLES + 1)),
            "too_many_trackables",
            id="too-many",
        ),
    ],
)
async def test_options_flow_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    trackable_codes: str,
    error: str,
) -> None:
    """Test invalid tracked trackable options."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_TRACKABLE_CODES: trackable_codes},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": error}
