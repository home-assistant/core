"""Tests for the NuHeat integration."""

from datetime import UTC, datetime
import json
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from chemelex_nuheat import (
    Account,
    NuHeatApiError,
    NuHeatAuthError,
    ScheduleMode,
    Thermostat,
    ThermostatMode,
)
import pytest

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.nuheat import async_setup_entry, async_unload_entry
from homeassistant.components.nuheat.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.nuheat.behavior import (
    api_mode_for_hvac_mode,
    api_mode_for_preset,
    hvac_mode_for_api_mode,
    preset_for_api_mode,
    setpoint_command_mode,
)
from homeassistant.components.nuheat.climate import (
    NuHeatClimateEntity,
    async_setup_entry as async_setup_climate,
)
from homeassistant.components.nuheat.config_flow import NuHeatConfigFlow
from homeassistant.components.nuheat.const import DOMAIN
from homeassistant.components.nuheat.coordinator import NuHeatCoordinator
from homeassistant.components.nuheat.migration import OAUTH_CONFIG_ENTRY_VERSION
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ACCESS_TOKEN,
    CONF_TOKEN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
    ServiceValidationError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    ImplementationUnavailableError,
    LocalOAuth2ImplementationWithPkce,
)
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from tests.common import MockConfigEntry
from tests.components.nuheat.helpers import jwt_access_token

ACCOUNT_SUBJECT = "synthetic-account-subject"


def thermostat(
    serial: str = "ABC123",
    *,
    mode: int = ThermostatMode.AUTO,
    heating: bool = True,
    online: bool = True,
) -> Thermostat:
    """Return a normalized API model for integration tests."""
    return Thermostat(
        serial_number=serial,
        name="Bathroom" if serial == "ABC123" else "Kitchen",
        current_temperature=21.5,
        target_temperature=23.0,
        heating=heating,
        online=online,
        mode=mode,
        hold_until=datetime(2026, 7, 8, 1, tzinfo=UTC),
    )


class FakeOAuthImplementation(AbstractOAuth2Implementation):
    """Minimal local/cloud OAuth provider for flow and refresh tests."""

    def __init__(self, *, token: dict | None = None, domain: str = "test") -> None:
        """Initialize the synthetic OAuth implementation."""
        self._token = token or {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }
        self._domain = domain

    @property
    def name(self) -> str:
        """Return the implementation name."""
        return "Test credentials"

    @property
    def domain(self) -> str:
        """Return the implementation domain."""
        return self._domain

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Return a synthetic authorization URL."""
        return "https://identity.example/authorize"

    async def async_resolve_external_data(self, external_data: object) -> dict:
        """Resolve synthetic OAuth callback data."""
        return dict(self._token)

    async def _async_refresh_token(self, token: dict) -> dict:
        return {
            **token,
            "access_token": "rotated-access",
            "refresh_token": "rotated-refresh",
            "expires_in": 3600,
        }


def oauth_data(
    access_token: str | None = None, *, subject: str = ACCOUNT_SUBJECT
) -> dict[str, Any]:
    """Return synthetic OAuth config-entry data."""
    return {
        "auth_implementation": "test",
        CONF_TOKEN: {CONF_ACCESS_TOKEN: access_token or jwt_access_token(subject)},
    }


def config_flow(hass: HomeAssistant, *, source: str = SOURCE_USER) -> NuHeatConfigFlow:
    """Return a NuHeat config flow attached to Home Assistant."""
    flow = NuHeatConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": source}
    return flow


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
    flow = config_flow(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(return_value={}),
    ):
        result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_oauth_credentials"
    strings = json.loads(
        Path("homeassistant/components/nuheat/strings.json").read_text()
    )
    assert strings["config"]["abort"]["missing_oauth_credentials"] == (
        "OAuth application credentials are required for this development build. "
        "A future official Home Assistant integration should use centrally managed "
        "credentials."
    )


@pytest.mark.asyncio
async def test_oauth_implementation_temporarily_unavailable(
    hass: HomeAssistant,
) -> None:
    """A cloud implementation lookup failure produces a translated abort."""
    flow = config_flow(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(side_effect=ImplementationUnavailableError("cloud unavailable")),
    ):
        result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_implementation_unavailable"


@pytest.mark.asyncio
async def test_config_flow_accepts_future_cloud_implementation(
    hass: HomeAssistant,
) -> None:
    """Test a centrally managed OAuth implementation can be selected."""
    cloud = FakeOAuthImplementation(domain="cloud")
    flow = config_flow(hass)
    flow.flow_id = "cloud-test-flow"
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(return_value={"cloud": cloud}),
    ):
        result = await flow.async_step_user()
        assert result["step_id"] == "pick_implementation"
        result = await flow.async_step_user({"implementation": "cloud"})
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"].startswith("https://identity.example/authorize")
    assert flow.flow_impl is cloud


@pytest.mark.asyncio
async def test_successful_oauth_setup(hass: HomeAssistant) -> None:
    """Test successful OAuth account setup."""
    flow = config_flow(hass)
    data = oauth_data()
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
        result = await flow.async_oauth_create_entry(data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Owner@Example.com"
    assert result["data"] == data
    assert flow.unique_id == ACCOUNT_SUBJECT


@pytest.mark.asyncio
async def test_duplicate_account_is_prevented(hass: HomeAssistant) -> None:
    """Test duplicate OAuth subjects cannot create another entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=oauth_data(), unique_id=ACCOUNT_SUBJECT)
    entry.add_to_hass(hass)
    flow = config_flow(hass)
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
        pytest.raises(AbortFlow, match="already_configured"),
    ):
        await flow.async_oauth_create_entry(oauth_data())


@pytest.mark.asyncio
async def test_duplicate_provisional_account_migrates_in_place_and_is_rejected(
    hass: HomeAssistant,
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
    flow = config_flow(hass)
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
        pytest.raises(AbortFlow, match="already_configured"),
    ):
        await flow.async_oauth_create_entry(oauth_data())

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
) -> None:
    """Test account lookup failures are translated without token logging."""
    flow = config_flow(hass)
    secret = jwt_access_token(ACCOUNT_SUBJECT, marker="must-not-be-logged")
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(side_effect=error),
        ),
    ):
        result = await flow.async_oauth_create_entry(oauth_data(secret))
    assert result["reason"] == reason
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_successful_reauthentication(hass: HomeAssistant) -> None:
    """Test successful reauthentication updates the existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id="owner@example.com",
        title="Owner@Example.com",
        version=2,
    )
    entry.add_to_hass(hass)
    flow = config_flow(hass, source=SOURCE_REAUTH)
    flow.context["entry_id"] = entry.entry_id
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
        new_data = oauth_data(subject=ACCOUNT_SUBJECT)
        result = await flow.async_oauth_create_entry(new_data)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == new_data
    assert entry.title == "Renamed@Example.com"
    assert entry.unique_id == ACCOUNT_SUBJECT
    assert entry.version == OAUTH_CONFIG_ENTRY_VERSION


@pytest.mark.asyncio
async def test_reauthentication_rejects_wrong_account(hass: HomeAssistant) -> None:
    """Test reauthentication rejects a different OAuth subject."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id=ACCOUNT_SUBJECT,
    )
    entry.add_to_hass(hass)
    flow = config_flow(hass, source=SOURCE_REAUTH)
    flow.context["entry_id"] = entry.entry_id
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
        pytest.raises(AbortFlow, match="reauth_account_mismatch"),
    ):
        await flow.async_oauth_create_entry(
            oauth_data(subject="different-synthetic-subject")
        )
    assert entry.data == oauth_data(subject=ACCOUNT_SUBJECT)


@pytest.mark.asyncio
async def test_same_username_with_different_subject_creates_distinct_account(
    hass: HomeAssistant,
) -> None:
    """Display usernames do not collapse distinct OAuth subjects."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(subject="first-synthetic-subject"),
        unique_id="first-synthetic-subject",
        title="Owner@Example.com",
    )
    existing.add_to_hass(hass)
    flow = config_flow(hass)
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
        result = await flow.async_oauth_create_entry(
            oauth_data(subject="second-synthetic-subject")
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == existing.title
    assert flow.unique_id == "second-synthetic-subject"


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
) -> None:
    """Invalid token identity cannot create or mutate an account entry."""
    flow = config_flow(hass)
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
        result = await flow.async_oauth_create_entry(oauth_data(access_token))

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
    api = AsyncMock()
    api.list_thermostats.side_effect = NuHeatAuthError("rejected")
    coordinator = NuHeatCoordinator(hass, entry, api)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


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
    await async_setup_climate(hass, entry, lambda entities: added.extend(entities))
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
        hass.config.units = IMPERIAL_SYSTEM
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.set_target_temperature.return_value = thermostat(mode=ThermostatMode.MANUAL)
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

    await entity.async_set_temperature(temperature=write)
    api.set_target_temperature.assert_awaited_once_with(
        "ABC123", pytest.approx(celsius), mode=ScheduleMode.HOLD
    )
    await entity.async_will_remove_from_hass()
    await coordinator.async_shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("preset", "schedule_mode", "api_mode"),
    [
        ("Run Schedule", ScheduleMode.AUTO, ThermostatMode.AUTO),
        ("Temporary Hold", ScheduleMode.HOLD, ThermostatMode.HOLD),
        ("Permanent Hold", ScheduleMode.MANUAL, ThermostatMode.MANUAL),
    ],
)
async def test_preset_and_mode_mapping(
    hass: HomeAssistant,
    preset: str,
    schedule_mode: ScheduleMode,
    api_mode: ThermostatMode,
) -> None:
    """Test Home Assistant presets map to NuHeat API modes."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.set_schedule_mode.return_value = thermostat(mode=api_mode)
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_preset_mode(preset)
    expected_temperature = None if preset == "Run Schedule" else 23.0
    api.set_schedule_mode.assert_awaited_once_with(
        "ABC123", schedule_mode, temperature=expected_temperature
    )
    assert preset_for_api_mode(api_mode) == preset
    assert api_mode_for_preset(preset) is schedule_mode


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hvac_mode", "schedule_mode", "api_mode", "temperature"),
    [
        (HVACMode.AUTO, ScheduleMode.AUTO, ThermostatMode.AUTO, None),
        (HVACMode.HEAT, ScheduleMode.MANUAL, ThermostatMode.MANUAL, 23.0),
    ],
)
async def test_legacy_hvac_mode_service_calls(
    hass: HomeAssistant,
    hvac_mode: HVACMode,
    schedule_mode: ScheduleMode,
    api_mode: ThermostatMode,
    temperature: float | None,
) -> None:
    """Existing AUTO and HEAT service calls retain their public behavior."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.set_schedule_mode.return_value = thermostat(mode=api_mode)
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    assert entity.hvac_modes == [HVACMode.AUTO, HVACMode.HEAT]
    assert entity.preset_modes == [
        "Run Schedule",
        "Temporary Hold",
        "Permanent Hold",
    ]

    await entity.async_set_hvac_mode(hvac_mode)

    api.set_schedule_mode.assert_awaited_once_with(
        "ABC123", schedule_mode, temperature=temperature
    )
    assert api_mode_for_hvac_mode(hvac_mode) is schedule_mode
    assert hvac_mode_for_api_mode(api_mode) is hvac_mode


@pytest.mark.parametrize(
    ("api_mode", "requested_hvac_mode", "expected"),
    [
        (ThermostatMode.AUTO, None, ScheduleMode.HOLD),
        (ThermostatMode.HOLD, None, ScheduleMode.HOLD),
        (ThermostatMode.MANUAL, None, ScheduleMode.MANUAL),
        (ThermostatMode.AUTO, HVACMode.HEAT, ScheduleMode.MANUAL),
    ],
)
def test_setpoint_compatibility_mapping(
    api_mode: ThermostatMode,
    requested_hvac_mode: HVACMode | None,
    expected: ScheduleMode,
) -> None:
    """Setpoints isolate temporary-Hold versus Manual compatibility policy."""
    assert setpoint_command_mode(api_mode, requested_hvac_mode) is expected


@pytest.mark.asyncio
async def test_unsupported_preset_uses_translated_exception(
    hass: HomeAssistant,
) -> None:
    """Invalid climate input raises HA's translatable validation error."""
    coordinator, _, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    with pytest.raises(ServiceValidationError) as raised:
        await entity.async_set_preset_mode("unsupported")
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "unsupported_preset"


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
        assert await async_setup_entry(hass, entry) is True
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
    entry = MockConfigEntry(domain=DOMAIN, data=oauth_data())
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
        pytest.raises(expected),
    ):
        await async_setup_entry(hass, entry)


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
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
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
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Unload forwards to the configured entity platforms."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ) as unload:
        assert await async_unload_entry(hass, entry) is True
    unload.assert_awaited_once()
