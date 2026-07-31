"""Tests for the NuHeat integration."""

from datetime import UTC, datetime
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from chemelex_nuheat import (
    Account,
    HoldUntilStatus,
    NuHeatApiError,
    NuHeatAuthError,
    ScheduleMode,
    Thermostat,
    ThermostatState,
)
import pytest

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.nuheat.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.nuheat.behavior import (
    api_mode_for_hvac_mode,
    api_mode_for_preset,
    hvac_mode_for_thermostat,
    preset_for_thermostat,
    setpoint_command_mode,
)
from homeassistant.components.nuheat.climate import (
    NuHeatClimateEntity,
    async_setup_entry as async_setup_climate,
)
from homeassistant.components.nuheat.const import (
    AUTHORIZE_URL,
    DOMAIN,
    OAUTH_SCOPES,
    PRESET_PERMANENT_HOLD,
    PRESET_RUN,
    PRESET_TEMPORARY_HOLD,
    TOKEN_URL,
)
from homeassistant.components.nuheat.coordinator import NuHeatCoordinator
from homeassistant.components.nuheat.migration import OAUTH_CONFIG_ENTRY_VERSION
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ACCESS_TOKEN,
    CONF_TOKEN,
    UnitOfTemperature,
)
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
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .helpers import FakeOAuthImplementation, complete_oauth_flow, jwt_access_token

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

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
async def test_missing_credentials_has_helpful_error(hass: HomeAssistant) -> None:
    """Test missing OAuth credentials produce a helpful abort."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(return_value={}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_oauth_credentials"


@pytest.mark.asyncio
async def test_oauth_implementation_temporarily_unavailable(
    hass: HomeAssistant,
) -> None:
    """A cloud implementation lookup failure produces a translated abort."""
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
        key: strings["abort"][key] for key in expected_abort_references
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
async def test_duplicate_provisional_account_migrates_in_place_and_is_rejected(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Fresh setup recognizes a stored subject behind a provisional ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Owner@Example.com",
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id="owner@example.com",
        version=2,
    )
    entry.add_to_hass(hass)
    entry_id = entry.entry_id
    original_data = entry.data
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
    assert entry.entry_id == entry_id
    assert entry.unique_id == ACCOUNT_SUBJECT
    assert entry.version == OAUTH_CONFIG_ENTRY_VERSION
    assert entry.data is original_data
    assert entry.title == "Owner@Example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (NuHeatAuthError("rejected"), "invalid_auth"),
        (NuHeatApiError("down"), "cannot_connect"),
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
    assert result["reason"] == reason
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
        unique_id="owner@example.com",
        title="Owner@Example.com",
        version=2,
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
    ("implementations", "reason"),
    [
        ({}, "missing_oauth_credentials"),
        (
            ImplementationUnavailableError("synthetic implementation outage"),
            "oauth_implementation_unavailable",
        ),
    ],
)
async def test_reauthentication_without_available_implementation(
    hass: HomeAssistant,
    implementations: dict[str, FakeOAuthImplementation] | Exception,
    reason: str,
) -> None:
    """Reauth reports unavailable implementations without indexing stored data."""
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
    ):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


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
    api.list_thermostats.side_effect = NuHeatAuthError("rejected")
    coordinator = NuHeatCoordinator(hass, entry, api)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_config_entry_first_refresh()

    api.list_thermostats.assert_awaited_once_with()
    assert coordinator.last_update_success is False
    assert coordinator.data is None


@pytest.mark.asyncio
async def test_dynamic_discovery_retains_entities_without_duplicates(
    hass: HomeAssistant,
) -> None:
    """Test coordinator updates discover entities without duplicates."""
    coordinator, api, entry = await coordinator_with(
        hass, thermostat(), thermostat("XYZ789")
    )
    entry.runtime_data = SimpleNamespace(coordinator=coordinator)
    added: list[NuHeatClimateEntity] = []
    await async_setup_climate(hass, entry, added.extend)
    assert {entity.unique_id for entity in added} == {"ABC123", "XYZ789"}

    api.list_thermostats.return_value = [thermostat(), thermostat("NEW456")]
    await coordinator.async_refresh()
    assert {entity.unique_id for entity in added} == {"ABC123", "XYZ789", "NEW456"}
    assert "XYZ789" in coordinator.data
    assert coordinator.is_thermostat_available("XYZ789") is False

    await coordinator.async_refresh()
    assert len(added) == 3
    await coordinator.async_shutdown()


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
    ("imperial", "unit", "current", "target", "minimum", "maximum", "write", "celsius"),
    [
        (False, UnitOfTemperature.CELSIUS, 21.5, 23.0, 7.0, 35.0, 24.0, 24.0),
        (True, UnitOfTemperature.FAHRENHEIT, 71.0, 73.0, 45.0, 95.0, 75.2, 24.0),
    ],
)
async def test_climate_state_and_writes_follow_ha_unit(
    hass: HomeAssistant,
    imperial: bool,
    unit: UnitOfTemperature,
    current: float,
    target: float,
    minimum: float,
    maximum: float,
    write: float,
    celsius: float,
) -> None:
    """Test climate reads and writes follow the configured unit system."""
    if imperial:
        hass.config.units = US_CUSTOMARY_SYSTEM
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.set_target_temperature.return_value = thermostat(
        mode=3,
        hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
    )
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    state = await add_entity_state(hass, entity, "climate.nuheat_test")

    assert entity.temperature_unit == unit
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == pytest.approx(current)
    assert state.attributes[ATTR_TEMPERATURE] == pytest.approx(target)
    assert state.attributes["min_temp"] == pytest.approx(minimum)
    assert state.attributes["max_temp"] == pytest.approx(maximum)
    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.hvac_action is HVACAction.HEATING
    assert entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert entity.supported_features & ClimateEntityFeature.TURN_OFF
    assert entity.supported_features & ClimateEntityFeature.TURN_ON

    await entity.async_set_temperature(temperature=write)
    api.set_target_temperature.assert_awaited_once_with(
        "ABC123",
        pytest.approx(celsius),
        mode=ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE,
        hold_until=datetime(2026, 7, 8, 1, tzinfo=UTC),
    )
    assert api.list_thermostats.await_count == 2
    await entity.async_will_remove_from_hass()
    await coordinator.async_shutdown()


@pytest.mark.asyncio
async def test_scheduled_target_change_holds_until_next_schedule(
    hass: HomeAssistant,
) -> None:
    """A scheduled setpoint write omits the end and refreshes the coordinator."""
    scheduled = thermostat(
        raw_target_temperature=0,
        hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
    )
    coordinator, api, _ = await coordinator_with(hass, scheduled)
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    await entity.async_set_temperature(temperature=22.0)

    api.set_target_temperature.assert_awaited_once_with(
        "ABC123", 22.0, mode=ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE
    )
    assert api.list_thermostats.await_count == 2


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
async def test_off_remains_optimistic_across_indistinguishable_get(
    hass: HomeAssistant,
) -> None:
    """A local OFF command survives GET data shared by Manual and Standby."""
    ambiguous = thermostat(
        mode=3,
        raw_target_temperature=0,
        hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
        heating=False,
    )
    coordinator, api, _ = await coordinator_with(hass, ambiguous)
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    assert entity.hvac_modes == [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    assert entity.hvac_mode is None
    assert entity.assumed_state is False

    await entity.async_set_hvac_mode(HVACMode.OFF)

    api.set_standby.assert_awaited_once_with("ABC123")
    assert api.list_thermostats.await_count == 2
    assert entity.hvac_mode is HVACMode.OFF
    assert entity.hvac_action is HVACAction.OFF
    assert entity.target_temperature is None
    assert entity.assumed_state is True

    # A newly created entity has no command memory and never infers OFF from
    # the same mode-3/null-hold/zero-target GET response.
    restarted_entity = NuHeatClimateEntity(coordinator, "ABC123")
    assert restarted_entity.hvac_mode is None
    assert restarted_entity.hvac_action is HVACAction.IDLE
    assert restarted_entity.target_temperature is None
    assert restarted_entity.assumed_state is False


@pytest.mark.asyncio
async def test_failed_standby_command_does_not_assume_off(
    hass: HomeAssistant,
) -> None:
    """OFF is remembered only after the Standby command succeeds."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.set_standby.side_effect = NuHeatApiError("write failed")
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    with pytest.raises(NuHeatApiError, match="write failed"):
        await entity.async_turn_off()

    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.assumed_state is False
    assert api.list_thermostats.await_count == 1


@pytest.mark.asyncio
async def test_turn_off_and_turn_on_use_standby_and_auto(
    hass: HomeAssistant,
) -> None:
    """The standard climate actions map to verified Standby and Auto writes."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    await entity.async_turn_off()
    api.set_standby.assert_awaited_once_with("ABC123")
    assert entity.hvac_mode is HVACMode.OFF

    await entity.async_turn_on()
    api.set_schedule_mode.assert_awaited_once_with("ABC123", ScheduleMode.AUTO)
    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.hvac_action is HVACAction.HEATING
    assert entity.target_temperature == 23.0
    assert entity.assumed_state is False
    # The coordinator debounces the two immediate post-command refreshes.
    assert api.list_thermostats.await_count == 2
    await coordinator.async_shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exit_command",
    ["auto", "heat", "target", "run-preset", "temporary-hold-preset"],
)
async def test_successful_control_command_clears_optimistic_off(
    hass: HomeAssistant, exit_command: str
) -> None:
    """Every supported command which exits Standby clears local OFF memory."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_turn_off()
    assert entity.assumed_state is True

    if exit_command == "auto":
        await entity.async_set_hvac_mode(HVACMode.AUTO)
    elif exit_command == "heat":
        await entity.async_set_hvac_mode(HVACMode.HEAT)
    elif exit_command == "target":
        await entity.async_set_temperature(temperature=22.0)
        api.set_target_temperature.assert_awaited_once_with(
            "ABC123", 22.0, mode=ScheduleMode.MANUAL
        )
    elif exit_command == "run-preset":
        await entity.async_set_preset_mode(PRESET_RUN)
    else:
        await entity.async_set_preset_mode(PRESET_TEMPORARY_HOLD)

    assert entity.assumed_state is False
    assert entity.hvac_mode is not HVACMode.OFF
    # The coordinator debounces the two immediate post-command refreshes.
    assert api.list_thermostats.await_count == 2
    await coordinator.async_shutdown()


@pytest.mark.parametrize(
    ("value", "expected_preset", "expected_hvac"),
    [
        (
            thermostat(
                raw_target_temperature=0,
                hold_until=None,
                hold_until_status=HoldUntilStatus.NULL,
            ),
            PRESET_RUN,
            HVACMode.AUTO,
        ),
        (thermostat(), PRESET_TEMPORARY_HOLD, HVACMode.AUTO),
        (
            thermostat(
                mode=3,
                hold_until=None,
                hold_until_status=HoldUntilStatus.NULL,
            ),
            PRESET_PERMANENT_HOLD,
            HVACMode.AUTO,
        ),
    ],
)
def test_live_read_state_mapping(
    value: Thermostat, expected_preset: str, expected_hvac: HVACMode
) -> None:
    """Only live-validated complete states receive presets and HVAC modes."""
    assert preset_for_thermostat(value) == expected_preset
    assert hvac_mode_for_thermostat(value) is expected_hvac


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("preset", "schedule_mode", "temperature"),
    [
        (PRESET_RUN, ScheduleMode.AUTO, None),
        (
            PRESET_TEMPORARY_HOLD,
            ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE,
            23.0,
        ),
    ],
)
async def test_validated_preset_commands(
    hass: HomeAssistant,
    preset: str,
    schedule_mode: ScheduleMode,
    temperature: float | None,
) -> None:
    """Only presets with documented command behavior issue writes."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.set_schedule_mode.return_value = thermostat()
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    await entity.async_set_preset_mode(preset)

    if temperature is None:
        api.set_schedule_mode.assert_awaited_once_with("ABC123", schedule_mode)
    else:
        api.set_schedule_mode.assert_awaited_once_with(
            "ABC123", schedule_mode, temperature=temperature
        )
    assert api_mode_for_preset(preset) is schedule_mode
    assert api.list_thermostats.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hvac_mode", "schedule_mode", "temperature"),
    [
        (HVACMode.AUTO, ScheduleMode.AUTO, None),
        (HVACMode.HEAT, ScheduleMode.MANUAL, 23.0),
    ],
)
async def test_legacy_hvac_command_support_remains_separate_from_read_state(
    hass: HomeAssistant,
    hvac_mode: HVACMode,
    schedule_mode: ScheduleMode,
    temperature: float | None,
) -> None:
    """AUTO and HEAT commands remain, without claiming a Manual readback."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    refreshed = (
        thermostat(
            raw_target_temperature=0,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        )
        if hvac_mode is HVACMode.AUTO
        else thermostat(
            mode=3,
            raw_target_temperature=0,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        )
    )
    api.list_thermostats.return_value = [refreshed]
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    assert entity.hvac_modes == [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    assert entity.preset_modes == [
        PRESET_RUN,
        PRESET_TEMPORARY_HOLD,
        PRESET_PERMANENT_HOLD,
    ]

    await entity.async_set_hvac_mode(hvac_mode)

    if temperature is None:
        api.set_schedule_mode.assert_awaited_once_with("ABC123", schedule_mode)
    else:
        api.set_schedule_mode.assert_awaited_once_with(
            "ABC123", schedule_mode, temperature=temperature
        )
    assert api_mode_for_hvac_mode(hvac_mode) is schedule_mode
    assert entity.hvac_mode is (HVACMode.AUTO if hvac_mode is HVACMode.AUTO else None)
    assert api.list_thermostats.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current",
    [
        thermostat(),
        thermostat(
            mode=3,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        ),
        thermostat(
            mode=3,
            raw_target_temperature=0,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        ),
        thermostat(
            raw_target_temperature=0,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        ),
    ],
    ids=["timed-hold", "permanent-hold", "manual-or-standby", "scheduled"],
)
async def test_auto_command_is_serial_only_for_every_read_state(
    hass: HomeAssistant, current: Thermostat
) -> None:
    """Auto uses one verified command to resume or exit every control state."""
    coordinator, api, _ = await coordinator_with(hass, current)
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    await entity.async_set_hvac_mode(HVACMode.AUTO)

    api.set_schedule_mode.assert_awaited_once_with("ABC123", ScheduleMode.AUTO)
    assert api.list_thermostats.await_count == 2


@pytest.mark.asyncio
async def test_bodyless_command_success_relies_on_coordinator_refresh(
    hass: HomeAssistant,
) -> None:
    """Core does not inspect a write result before requesting fresh state."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.set_schedule_mode.return_value = None
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    await entity.async_set_hvac_mode(HVACMode.AUTO)

    api.set_schedule_mode.assert_awaited_once_with("ABC123", ScheduleMode.AUTO)
    assert api.list_thermostats.await_count == 2


def test_setpoint_command_mapping_uses_derived_state() -> None:
    """Setpoints never infer Manual from numeric mode 3 alone."""
    scheduled = thermostat(
        raw_target_temperature=0,
        hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
    )
    permanent = thermostat(
        mode=3,
        hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
    )
    ambiguous = thermostat(
        mode=3,
        raw_target_temperature=0,
        hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
    )
    unknown = thermostat(
        mode=999,
        raw_target_temperature=0,
        hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
    )

    assert setpoint_command_mode(scheduled) is ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE
    assert setpoint_command_mode(thermostat()) is ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE
    assert setpoint_command_mode(ambiguous, HVACMode.HEAT) is ScheduleMode.MANUAL
    for value in (permanent, ambiguous, unknown):
        with pytest.raises(ValueError, match="Unsupported thermostat state"):
            setpoint_command_mode(value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        thermostat(
            mode=3,
            raw_target_temperature=0,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        ),
        thermostat(
            mode=999,
            raw_target_temperature=0,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        ),
    ],
)
async def test_ambiguous_and_unknown_states_remain_available_but_unlabeled(
    hass: HomeAssistant, value: Thermostat
) -> None:
    """Unknown read semantics do not make an online thermostat unavailable."""
    coordinator, api, _ = await coordinator_with(hass, value)
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    assert entity.available is True
    assert entity.target_temperature is None
    assert entity.hvac_mode is None
    assert entity.preset_mode is None
    assert value.state in (
        ThermostatState.AMBIGUOUS_MANUAL_OR_STANDBY,
        ThermostatState.UNKNOWN,
    )
    with pytest.raises(ServiceValidationError) as raised:
        await entity.async_set_temperature(temperature=22.0)
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "unsupported_state"
    api.set_target_temperature.assert_not_awaited()


@pytest.mark.asyncio
async def test_permanent_hold_is_readable_but_not_writable(
    hass: HomeAssistant,
) -> None:
    """Permanent Hold has a dedicated translated error for its unknown write."""
    permanent = thermostat(
        mode=3,
        hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
    )
    coordinator, api, _ = await coordinator_with(hass, permanent)
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    assert entity.preset_mode == PRESET_PERMANENT_HOLD
    with pytest.raises(ServiceValidationError) as raised:
        await entity.async_set_preset_mode(PRESET_PERMANENT_HOLD)
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "indefinite_hold_unsupported"
    api.set_schedule_mode.assert_not_awaited()


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


def test_climate_preset_translations() -> None:
    """All NuHeat preset labels are supplied through entity translations."""
    strings = load_json("homeassistant/components/nuheat/strings.json")
    assert strings["entity"]["climate"]["thermostat"]["state_attributes"][
        "preset_mode"
    ]["state"] == {
        PRESET_PERMANENT_HOLD: "Permanent hold",
        PRESET_RUN: "Run schedule",
        PRESET_TEMPORARY_HOLD: "Temporary hold",
    }
    assert strings["exceptions"]["indefinite_hold_unsupported"]["message"] == (
        "Creating an indefinite hold is not supported by the documented NuHeat API."
    )


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
        "async_unload_platforms",
        AsyncMock(return_value=True),
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
