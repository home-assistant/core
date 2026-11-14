"""Tests for the NuHeat integration."""

from datetime import UTC, datetime
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from chemelex_nuheat import (
    Account,
    HoldUntilStatus,
    NuHeatApiError,
    NuHeatAuthError,
    NuHeatRateLimitError,
    Thermostat,
    ThermostatState,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.climate import HVACAction
from homeassistant.components.nuheat.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.nuheat.climate import NuHeatClimateEntity
from homeassistant.components.nuheat.const import (
    AUTHORIZE_URL,
    DOMAIN,
    OAUTH_SCOPES,
    TOKEN_URL,
)
from homeassistant.components.nuheat.coordinator import NuHeatCoordinator
from homeassistant.components.nuheat.migration import OAUTH_CONFIG_ENTRY_VERSION
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
    ServiceValidationError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    LocalOAuth2ImplementationWithPkce,
)
from homeassistant.util.json import load_json

from .helpers import FakeOAuthImplementation, complete_oauth_flow, jwt_access_token

ACCOUNT_SUBJECT = "synthetic-account-subject"


def test_official_oauth_endpoints_and_scopes() -> None:
    """Test OAuth constants match the current official NAM documentation."""
    assert AUTHORIZE_URL == "https://identity.nam.mynuheat.com/connect/authorize"
    assert TOKEN_URL == "https://identity.nam.mynuheat.com/connect/token"
    assert OAUTH_SCOPES == ("openid", "openapi", "offline_access")


def thermostat(
    serial: str = "ABC123",
    *,
    mode: int = 2,
    raw_target_temperature: float | None = 2300,
    hold_until: datetime | None = datetime(2026, 7, 8, 1, tzinfo=UTC),
    hold_until_status: HoldUntilStatus = HoldUntilStatus.VALUE,
    heating: bool = True,
    online: bool = True,
) -> Thermostat:
    """Return a normalized API model for integration tests."""
    return Thermostat(
        serial_number=serial,
        name="Bathroom" if serial == "ABC123" else "Kitchen",
        current_temperature=21.5,
        target_temperature=(
            None
            if raw_target_temperature in (None, 0)
            else float(raw_target_temperature) / 100
        ),
        heating=heating,
        online=online,
        mode=mode,
        raw_target_temperature=raw_target_temperature,
        hold_until=hold_until,
        raw_hold_until=hold_until.isoformat() if hold_until is not None else None,
        hold_until_status=hold_until_status,
    )


def oauth_data(
    access_token: str | None = None, *, subject: str = ACCOUNT_SUBJECT
) -> dict[str, Any]:
    """Return synthetic OAuth config-entry data."""
    return {
        "auth_implementation": "test",
        CONF_TOKEN: {
            CONF_ACCESS_TOKEN: (
                jwt_access_token(subject) if access_token is None else access_token
            )
        },
    }


def oauth_implementation(
    access_token: str | None = None,
    *,
    subject: str = ACCOUNT_SUBJECT,
    domain: str = "test",
) -> FakeOAuthImplementation:
    """Return a synthetic implementation with a valid OAuth token response."""
    return FakeOAuthImplementation(
        token={
            CONF_ACCESS_TOKEN: (
                jwt_access_token(subject) if access_token is None else access_token
            ),
            "refresh_token": "synthetic-refresh-token",
            "expires_in": 3600,
        },
        domain=domain,
    )


async def coordinator_with(
    hass: HomeAssistant, *thermostats: Thermostat
) -> tuple[NuHeatCoordinator, AsyncMock, MockConfigEntry]:
    """Return a refreshed coordinator with synthetic thermostats."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    api = AsyncMock()
    api.cooldown_remaining = 0.0
    api.list_thermostats.return_value = list(thermostats)
    coordinator = NuHeatCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    return coordinator, api, entry


@pytest.mark.asyncio
@pytest.mark.parametrize("client_secret", ["issued-client-secret", ""])
async def test_local_application_credentials_path(
    hass: HomeAssistant, client_secret: str
) -> None:
    """Test local Application Credentials retain PKCE behavior."""
    implementation = await async_get_auth_implementation(
        hass,
        "local-test",
        ClientCredential("issued-client-id", client_secret),
    )
    assert isinstance(implementation, LocalOAuth2ImplementationWithPkce)
    assert implementation.domain == "local-test"
    assert implementation.client_id == "issued-client-id"
    assert implementation.extra_authorize_data["code_challenge_method"] == "S256"
    assert len(implementation.extra_token_resolve_data["code_verifier"]) == 128


@pytest.mark.asyncio
async def test_cloud_disabled_without_local_credentials(hass: HomeAssistant) -> None:
    """Official setup requires the cloud component, not user-supplied secrets."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(return_value={}),
    ) as get_implementations:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    get_implementations.assert_not_called()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cloud_not_enabled"
    assert result["description_placeholders"] == {"default_config": "default_config"}


async def test_local_credentials_without_cloud(hass: HomeAssistant) -> None:
    """Local credentials cannot bypass the cloud availability guard."""
    implementation = await async_get_auth_implementation(
        hass, "local-test", ClientCredential("synthetic-client", "synthetic-secret")
    )
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        return_value={"local-test": implementation},
    ) as get_implementations:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    get_implementations.assert_not_called()
    assert "cloud" not in hass.config.components
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cloud_not_enabled"


@pytest.mark.asyncio
async def test_oauth_implementation_temporarily_unavailable(
    hass: HomeAssistant,
) -> None:
    """A cloud implementation lookup failure produces a translated abort."""
    hass.config.components.add("cloud")
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(side_effect=ImplementationUnavailableError("cloud unavailable")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_implementation_unavailable"


def test_oauth_translation_structure() -> None:
    """Test all OAuth aborts and the implementation picker are translated."""
    strings = load_json("homeassistant/components/nuheat/strings.json")["config"]
    shared_aborts = load_json("homeassistant/components/homeassistant/strings.json")[
        "config"
    ]["abort"]
    expected_abort_references = {
        "already_configured": "[%key:common::config_flow::abort::already_configured_account%]",
        "already_in_progress": "[%key:common::config_flow::abort::already_in_progress%]",
        "authorize_url_timeout": "[%key:common::config_flow::abort::oauth2_authorize_url_timeout%]",
        "missing_configuration": "[%key:common::config_flow::abort::oauth2_missing_configuration%]",
        "missing_credentials": "[%key:common::config_flow::abort::oauth2_missing_credentials%]",
        "no_url_available": "[%key:common::config_flow::abort::oauth2_no_url_available%]",
        "oauth_error": "[%key:common::config_flow::abort::oauth2_error%]",
        "oauth_failed": "[%key:common::config_flow::abort::oauth2_failed%]",
        "oauth_implementation_unavailable": "[%key:common::config_flow::abort::oauth2_implementation_unavailable%]",
        "oauth_timeout": "[%key:common::config_flow::abort::oauth2_timeout%]",
        "oauth_unauthorized": "[%key:common::config_flow::abort::oauth2_unauthorized%]",
        "reauth_successful": "[%key:common::config_flow::abort::reauth_successful%]",
        "user_rejected_authorize": "[%key:common::config_flow::abort::oauth2_user_rejected_authorize%]",
    }
    assert {
        key: (shared_aborts | strings["abort"])[key]
        for key in expected_abort_references
    } == expected_abort_references
    assert strings["step"]["pick_implementation"] == {
        "data": {"implementation": "[%key:common::config_flow::data::implementation%]"},
        "data_description": {
            "implementation": "[%key:common::config_flow::description::implementation%]"
        },
        "title": "[%key:common::config_flow::title::oauth2_pick_implementation%]",
    }


@pytest.mark.asyncio
async def test_config_flow_accepts_future_cloud_implementation(
    hass: HomeAssistant,
) -> None:
    """Test a centrally managed OAuth implementation can be selected."""
    hass.config.components.add("cloud")
    local = FakeOAuthImplementation(domain="local")
    cloud = FakeOAuthImplementation(domain="cloud")
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(return_value={"local": local, "cloud": cloud}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick_implementation"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"implementation": "cloud"}
        )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"].startswith("https://identity.example/authorize")


@pytest.mark.asyncio
async def test_successful_oauth_setup(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test successful OAuth account setup."""
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account("Owner@Example.com")),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat()]),
        ),
    ):
        result = await complete_oauth_flow(
            hass, hass_client_no_auth, oauth_implementation()
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Owner@Example.com"
    assert result["data"]["auth_implementation"] == "test"
    assert result["data"][CONF_TOKEN][CONF_ACCESS_TOKEN] == jwt_access_token()
    assert result["result"].unique_id == ACCOUNT_SUBJECT


@pytest.mark.asyncio
async def test_oauth_setup_uses_fallback_for_nullable_account_name(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """A nullable documented userName does not prevent account setup."""
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account(None)),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat()]),
        ),
    ):
        result = await complete_oauth_flow(
            hass, hass_client_no_auth, oauth_implementation()
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NuHeat"


@pytest.mark.asyncio
async def test_duplicate_account_is_prevented(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test duplicate OAuth subjects cannot create another entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=oauth_data(), unique_id=ACCOUNT_SUBJECT)
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account("Owner@Example.com")),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat()]),
        ),
    ):
        result = await complete_oauth_flow(
            hass, hass_client_no_auth, oauth_implementation()
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (NuHeatAuthError("rejected"), "invalid_auth"),
        (NuHeatApiError("down"), "cannot_connect"),
        (NuHeatRateLimitError(60), "rate_limited"),
    ],
)
async def test_account_lookup_failures(
    hass: HomeAssistant,
    error: Exception,
    reason: str,
    caplog: pytest.LogCaptureFixture,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test account lookup failures are translated without token logging."""
    secret = jwt_access_token(ACCOUNT_SUBJECT, marker="must-not-be-logged")
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(side_effect=error),
        ),
    ):
        result = await complete_oauth_flow(
            hass, hass_client_no_auth, oauth_implementation(secret)
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert secret not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("implementation_domain", ["test", "alternate"])
async def test_successful_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    implementation_domain: str,
) -> None:
    """Reauth can use the stored implementation or an available replacement."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id=ACCOUNT_SUBJECT,
        title="Owner@Example.com",
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account("Renamed@Example.com")),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat()]),
        ),
    ):
        result = await complete_oauth_flow(
            hass,
            hass_client_no_auth,
            oauth_implementation(subject=ACCOUNT_SUBJECT, domain=implementation_domain),
            entry=entry,
            confirmation_step="reauth_confirm",
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["auth_implementation"] == implementation_domain
    assert entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN] == jwt_access_token(
        ACCOUNT_SUBJECT
    )
    assert entry.title == "Renamed@Example.com"
    assert entry.unique_id == ACCOUNT_SUBJECT
    assert entry.version == OAUTH_CONFIG_ENTRY_VERSION


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cloud_enabled", "implementations", "reason"),
    [
        (False, {}, "cloud_not_enabled"),
        (True, {}, "missing_credentials"),
        (
            True,
            ImplementationUnavailableError("synthetic implementation outage"),
            "oauth_implementation_unavailable",
        ),
    ],
)
async def test_reauthentication_without_available_implementation(
    hass: HomeAssistant,
    cloud_enabled: bool,
    implementations: dict[str, FakeOAuthImplementation] | Exception,
    reason: str,
) -> None:
    """Reauth reports unavailable implementations without indexing stored data."""
    if cloud_enabled:
        hass.config.components.add("cloud")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id=ACCOUNT_SUBJECT,
        title="Owner@Example.com",
    )
    entry.add_to_hass(hass)
    effect = (
        {"return_value": implementations}
        if isinstance(implementations, dict)
        else {"side_effect": implementations}
    )
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(**effect),
    ) as get_implementations:
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    if not cloud_enabled:
        get_implementations.assert_not_called()


@pytest.mark.asyncio
async def test_reauthentication_rejects_wrong_account(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test reauthentication rejects a different OAuth subject."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id=ACCOUNT_SUBJECT,
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account("Owner@Example.com")),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat()]),
        ),
    ):
        result = await complete_oauth_flow(
            hass,
            hass_client_no_auth,
            oauth_implementation(subject="different-synthetic-subject"),
            entry=entry,
            confirmation_step="reauth_confirm",
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"
    assert entry.data == oauth_data(subject=ACCOUNT_SUBJECT)


@pytest.mark.asyncio
async def test_same_username_with_different_subject_creates_distinct_account(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Display usernames do not collapse distinct OAuth subjects."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(subject="first-synthetic-subject"),
        unique_id="first-synthetic-subject",
        title="Owner@Example.com",
    )
    existing.add_to_hass(hass)
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account("Owner@Example.com")),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat()]),
        ),
    ):
        result = await complete_oauth_flow(
            hass,
            hass_client_no_auth,
            oauth_implementation(subject="second-synthetic-subject"),
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == existing.title
    assert result["result"].unique_id == "second-synthetic-subject"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "access_token",
    [
        "malformed",
        jwt_access_token(None),
        jwt_access_token(""),
        jwt_access_token("   "),
    ],
)
async def test_missing_or_malformed_subject_aborts_without_api_calls(
    hass: HomeAssistant,
    access_token: str,
    caplog: pytest.LogCaptureFixture,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Invalid token identity cannot create or mutate an account entry."""
    get_account = AsyncMock()
    list_thermostats = AsyncMock()
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            get_account,
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            list_thermostats,
        ),
    ):
        result = await complete_oauth_flow(
            hass, hass_client_no_auth, oauth_implementation(access_token)
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_account_identity"
    get_account.assert_not_awaited()
    list_thermostats.assert_not_awaited()
    assert access_token not in caplog.text
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.asyncio
async def test_coordinator_first_refresh_and_offline_availability(
    hass: HomeAssistant,
) -> None:
    """Test initial polling and offline thermostat availability."""
    coordinator, api, _ = await coordinator_with(
        hass, thermostat(), thermostat("XYZ789", online=False)
    )
    assert set(coordinator.data) == {"ABC123", "XYZ789"}
    assert coordinator.is_thermostat_available("ABC123") is True
    assert coordinator.is_thermostat_available("XYZ789") is False
    api.list_thermostats.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_coordinator_auth_failure_triggers_reauthentication(
    hass: HomeAssistant,
) -> None:
    """Polling auth rejection uses ConfigEntryAuthFailed for HA reauth."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    api = AsyncMock()
    api.cooldown_remaining = 0.0
    api.list_thermostats.side_effect = NuHeatAuthError("rejected")
    coordinator = NuHeatCoordinator(hass, entry, api)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_config_entry_first_refresh()

    api.list_thermostats.assert_awaited_once_with()
    assert coordinator.last_update_success is False
    assert coordinator.data is None


async def add_entity_state(
    hass: HomeAssistant, entity: NuHeatClimateEntity, entity_id: str
) -> State:
    """Add an entity and return its Home Assistant state."""
    entity.hass = hass
    entity.entity_id = entity_id
    await entity.async_added_to_hass()
    entity.async_write_ha_state()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("heating", "expected"),
    [(True, HVACAction.HEATING), (False, HVACAction.IDLE)],
)
async def test_hvac_action_follows_is_heating(
    hass: HomeAssistant, heating: bool, expected: HVACAction
) -> None:
    """The API activity flag is authoritative for climate action."""
    coordinator, _, _ = await coordinator_with(hass, thermostat(heating=heating))
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    assert entity.hvac_action is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        thermostat(
            mode=999,
            raw_target_temperature=0,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        ),
    ],
)
async def test_unknown_state_remains_available_but_unlabeled(
    hass: HomeAssistant, value: Thermostat
) -> None:
    """Unknown read semantics do not make an online thermostat unavailable."""
    coordinator, api, _ = await coordinator_with(hass, value)
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    assert entity.available is True
    assert entity.native_target_temperature is None
    assert entity.hvac_mode is None
    assert entity.preset_mode is None
    assert value.state is ThermostatState.UNKNOWN
    with pytest.raises(ServiceValidationError) as raised:
        await entity.async_set_temperature(temperature=22.0)
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "unsupported_state"
    api.set_target_temperature.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_preset_uses_translated_exception(
    hass: HomeAssistant,
) -> None:
    """Unknown presets continue to use the generic translated error."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    with pytest.raises(ServiceValidationError) as raised:
        await entity.async_set_preset_mode("unsupported")
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "unsupported_preset"
    api.set_schedule_mode.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_token_rotation_is_stored(hass: HomeAssistant) -> None:
    """Test rotated refresh tokens are persisted in the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "test",
            CONF_TOKEN: {
                "access_token": "expired-access",
                "refresh_token": "old-refresh",
                "expires_at": time.time() - 60,
                "expires_in": 0,
            },
        },
        unique_id=ACCOUNT_SUBJECT,
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.nuheat.async_get_config_entry_implementation",
            AsyncMock(return_value=FakeOAuthImplementation()),
        ),
        patch(
            "homeassistant.components.nuheat.NuHeatCoordinator.async_config_entry_first_refresh",
            AsyncMock(),
        ),
        patch("homeassistant.components.nuheat.async_get_clientsession"),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_TOKEN]["access_token"] == "rotated-access"
    assert entry.data[CONF_TOKEN]["refresh_token"] == "rotated-refresh"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            OAuth2TokenRequestReauthError(domain=DOMAIN, request_info=MagicMock()),
            ConfigEntryAuthFailed,
        ),
        (
            OAuth2TokenRequestTransientError(domain=DOMAIN, request_info=MagicMock()),
            ConfigEntryNotReady,
        ),
    ],
)
async def test_rejected_and_transient_refresh_tokens(
    hass: HomeAssistant, error: Exception, expected: type[Exception]
) -> None:
    """Test token refresh failures map to setup exceptions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(),
        unique_id=ACCOUNT_SUBJECT,
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.nuheat.async_get_config_entry_implementation",
            AsyncMock(return_value=FakeOAuthImplementation()),
        ),
        patch(
            "homeassistant.components.nuheat.OAuth2Session.async_ensure_token_valid",
            AsyncMock(side_effect=error),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is False

    assert entry.state is (
        ConfigEntryState.SETUP_ERROR
        if expected is ConfigEntryAuthFailed
        else ConfigEntryState.SETUP_RETRY
    )


@pytest.mark.asyncio
async def test_setup_cloud_failure_is_retryable(hass: HomeAssistant) -> None:
    """A temporary failure during the initial coordinator poll retries setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "test",
            CONF_TOKEN: {
                "access_token": "valid-access",
                "refresh_token": "refresh",
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
            },
        },
        unique_id=ACCOUNT_SUBJECT,
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.nuheat.async_get_config_entry_implementation",
            AsyncMock(return_value=FakeOAuthImplementation()),
        ),
        patch("homeassistant.components.nuheat.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.NuHeatClient.list_thermostats",
            AsyncMock(side_effect=NuHeatApiError("temporary cloud failure")),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is False
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.asyncio
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Unload forwards to the configured entity platforms."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        AsyncMock(),
    ) as unload:
        assert await hass.config_entries.async_unload(entry.entry_id) is True
    unload.assert_awaited_once()


@pytest.mark.asyncio
async def test_config_flow_client_uses_access_token_callback(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test the config-flow API client receives its OAuth token callback."""

    class CallbackClient:
        def __init__(self, _session, callback) -> None:
            self._callback = callback

        async def get_account(self) -> Account:
            assert await self._callback(False) == jwt_access_token()
            return Account("Owner@Example.com")

        async def list_thermostats(self) -> list[Thermostat]:
            return [thermostat()]

    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient", CallbackClient
        ),
    ):
        result = await complete_oauth_flow(
            hass, hass_client_no_auth, oauth_implementation()
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_reauth_with_malformed_stored_identity(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test malformed old identity data cannot bypass account matching."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: {CONF_ACCESS_TOKEN: "malformed"}},
        unique_id="provisional",
        version=2,
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account("Owner@Example.com")),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat()]),
        ),
    ):
        result = await complete_oauth_flow(
            hass,
            hass_client_no_auth,
            oauth_implementation(),
            entry=entry,
            confirmation_step="reauth_confirm",
        )
    assert result["reason"] == "reauth_account_mismatch"


@pytest.mark.asyncio
async def test_new_setup_skips_malformed_existing_identity(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test malformed unrelated entry data is ignored during duplicate lookup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: {CONF_ACCESS_TOKEN: "malformed"}},
        unique_id="unrelated",
        version=3,
    ).add_to_hass(hass)
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account("Owner@Example.com")),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat()]),
        ),
    ):
        result = await complete_oauth_flow(
            hass, hass_client_no_auth, oauth_implementation()
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
