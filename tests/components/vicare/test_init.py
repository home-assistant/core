"""Test ViCare initialization and migration."""

from datetime import timedelta
from unittest.mock import Mock, call, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from PyViCare.PyViCareUtils import (
    PyViCareInternalServerError,
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)

from homeassistant.components.vicare.const import DEFAULT_CACHE_DURATION, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from . import MODULE
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_v1_1_to_v2_1(hass: HomeAssistant) -> None:
    """Test migration of config entry from v1.1 through to v2.1."""
    mock_token = {
        "access_token": "mock-access-token",
        "refresh_token": "mock-refresh-token",
        "expires_at": 9999999999.0,
        "token_type": "Bearer",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
            "heating_type": "auto",
        },
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.obtain_token_via_basic_auth_pkce",
        return_value=mock_token,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert "heating_type" not in config_entry.data
    assert "username" not in config_entry.data
    assert "password" not in config_entry.data
    assert "client_id" not in config_entry.data
    assert config_entry.data["auth_implementation"] == DOMAIN
    assert config_entry.data["token"]["refresh_token"] == "mock-refresh-token"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_v1_2_to_v2_1(hass: HomeAssistant) -> None:
    """Test migration of config entry from v1.2 to v2.1."""
    mock_token = {
        "access_token": "mock-access-token",
        "refresh_token": "mock-refresh-token",
        "expires_at": 9999999999.0,
        "token_type": "Bearer",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.obtain_token_via_basic_auth_pkce",
        return_value=mock_token,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert "username" not in config_entry.data
    assert "password" not in config_entry.data
    assert "client_id" not in config_entry.data
    assert config_entry.data["auth_implementation"] == DOMAIN
    assert config_entry.data["token"]["refresh_token"] == "mock-refresh-token"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_token_failure(hass: HomeAssistant) -> None:
    """Test migration completes even when token cannot be obtained."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.obtain_token_via_basic_auth_pkce",
        return_value={},
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert "username" not in config_entry.data
    assert "password" not in config_entry.data
    assert "client_id" not in config_entry.data
    assert config_entry.data["auth_implementation"] == DOMAIN
    assert config_entry.data["token"] == {}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_creates_repair_issue(hass: HomeAssistant) -> None:
    """Test migration creates a repair issue for redirect URI update."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.obtain_token_via_basic_auth_pkce",
        return_value={
            "access_token": "a",
            "refresh_token": "r",
            "expires_at": 9999999999.0,
            "token_type": "Bearer",
        },
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "update_redirect_uri")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_v1_3_stamp_bump(hass: HomeAssistant) -> None:
    """Test pre-merge v1.3 entries are promoted to v2.1 without re-running migration."""
    token = {
        "access_token": "a",
        "refresh_token": "r",
        "expires_at": 9999999999.0,
        "token_type": "Bearer",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={"auth_implementation": DOMAIN, "token": token},
        version=1,
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.data["auth_implementation"] == DOMAIN
    assert config_entry.data["token"] == token


async def test_setup_entry_token_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed on invalid token."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=KeyError("token"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_implementation_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed when OAuth2 implementation is missing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        side_effect=ValueError("Implementation not available"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_token_refresh_transient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryNotReady on transient token refresh error."""
    mock_config_entry.add_to_hass(hass)

    request_info = Mock()
    request_info.real_url = "https://example.com"
    transient = OAuth2TokenRequestTransientError(
        domain=DOMAIN, request_info=request_info, status=503
    )
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=transient,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_token_refresh_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed when token refresh requires re-auth."""
    mock_config_entry.add_to_hass(hass)

    request_info = Mock()
    request_info.real_url = "https://example.com"
    reauth = OAuth2TokenRequestReauthError(
        domain=DOMAIN, request_info=request_info, status=401
    )
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=reauth,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_transient_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryNotReady on transient auth error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError("connection failed"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_invalid_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed on PyViCare credentials error."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            side_effect=PyViCareInvalidCredentialsError,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_invalid_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed on PyViCare config error."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            side_effect=PyViCareInvalidConfigurationError,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


# Device migration test can be removed in 2025.4.0
async def test_device_and_entity_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the device registry is updated correctly."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
        Fixture({"type:boiler"}, "vicare/dummy-device-no-serial.json"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.CLIMATE]),
    ):
        mock_config_entry.add_to_hass(hass)

        # device with serial data point
        device0 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway0"),
            },
            model="model0",
        )
        entry0 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway0-0",
            translation_key="heating",
            device_id=device0.id,
        )
        entry1 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway0_deviceSerialVitodens300W-heating-1",
            translation_key="heating",
            device_id=device0.id,
        )
        # device without serial data point
        device1 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway1"),
            },
            model="model1",
        )
        entry2 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway1-0",
            translation_key="heating",
            device_id=device1.id,
        )
        # device is not provided by api
        device2 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway2"),
            },
            model="model2",
        )
        entry3 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway2-0",
            translation_key="heating",
            device_id=device2.id,
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entry0.entity_id).unique_id
        == "gateway0_deviceSerialVitodens300W-heating-0"
    )
    assert (
        entity_registry.async_get(entry1.entity_id).unique_id
        == "gateway0_deviceSerialVitodens300W-heating-1"
    )
    assert (
        entity_registry.async_get(entry2.entity_id).unique_id
        == "gateway1_deviceId1-heating-0"
    )
    assert entity_registry.async_get(entry3.entity_id).unique_id == "gateway2-0"


async def test_coordinator_recovers_after_transient_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A transient fetch failure flips sensors unavailable, recovery restores them."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
    mock_vicare = MockPyViCare(fixtures)
    service = mock_vicare.devices[0].service

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=mock_vicare.as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensor_id = "sensor.model0_outside_temperature"
        state = hass.states.get(sensor_id)
        assert state is not None, f"{sensor_id} not found in states"
        assert state.state != STATE_UNAVAILABLE

        service.fetch_all_features.side_effect = PyViCareInternalServerError(
            {
                "statusCode": 500,
                "errorType": "INTERNAL_SERVER_ERROR",
                "message": "Internal Server Error",
                "viErrorId": "0",
            }
        )
        freezer.tick(timedelta(seconds=120))
        async_fire_time_changed(hass, fire_all=True)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(sensor_id)
        assert state.state == STATE_UNAVAILABLE

        service.fetch_all_features.side_effect = None
        freezer.tick(timedelta(seconds=120))
        async_fire_time_changed(hass, fire_all=True)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(sensor_id)
        assert state.state != STATE_UNAVAILABLE


async def test_per_device_failure_isolation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A transient failure on one gateway must not affect another gateway's sensors."""
    # Each fixture sits behind its own gateway (gateway0, gateway1), so the two
    # devices get separate coordinators and fail independently.
    fixtures: list[Fixture] = [
        Fixture({"type:climateSensor"}, "vicare/RoomSensor1.json"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor2.json"),
    ]
    mock_vicare = MockPyViCare(fixtures)
    service0 = mock_vicare.devices[0].service

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=mock_vicare.as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    sensor_device0 = "sensor.model0_temperature"
    sensor_device1 = "sensor.model1_temperature"

    assert hass.states.get(sensor_device0) is not None, f"{sensor_device0} not found"
    assert hass.states.get(sensor_device1) is not None, f"{sensor_device1} not found"
    assert hass.states.get(sensor_device0).state != STATE_UNAVAILABLE
    assert hass.states.get(sensor_device1).state != STATE_UNAVAILABLE

    service0.fetch_all_features.side_effect = PyViCareInternalServerError(
        {
            "statusCode": 500,
            "errorType": "INTERNAL_SERVER_ERROR",
            "message": "Internal Server Error",
            "viErrorId": "0",
        }
    )

    # Coordinator interval scales by gateway count (60 * 2 = 120s); tick past it.
    freezer.tick(timedelta(seconds=300))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(sensor_device0).state == STATE_UNAVAILABLE
    assert hass.states.get(sensor_device1).state != STATE_UNAVAILABLE


async def test_devices_on_same_gateway_share_coordinator(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Two devices behind one gateway share one coordinator and one fetch."""
    fixtures: list[Fixture] = [
        Fixture({"type:climateSensor"}, "vicare/RoomSensor1.json", gateway="gwA"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor2.json", gateway="gwA"),
    ]
    mock_vicare = MockPyViCare(fixtures)
    service0 = mock_vicare.devices[0].service

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=mock_vicare.as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensor_device0 = "sensor.model0_temperature"
        sensor_device1 = "sensor.model1_temperature"
        assert hass.states.get(sensor_device0).state != STATE_UNAVAILABLE
        assert hass.states.get(sensor_device1).state != STATE_UNAVAILABLE

        # The gateway's single fetch failing takes every device on it offline.
        service0.fetch_all_features.side_effect = PyViCareInternalServerError(
            {
                "statusCode": 500,
                "errorType": "INTERNAL_SERVER_ERROR",
                "message": "Internal Server Error",
                "viErrorId": "0",
            }
        )
        # One gateway -> interval 60s; tick past it.
        freezer.tick(timedelta(seconds=120))
        async_fire_time_changed(hass, fire_all=True)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(sensor_device0).state == STATE_UNAVAILABLE
        assert hass.states.get(sensor_device1).state == STATE_UNAVAILABLE


async def test_coordinator_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An auth error during coordinator refresh starts a reauth flow."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
    mock_vicare = MockPyViCare(fixtures)
    service = mock_vicare.devices[0].service

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=mock_vicare.as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert not [
            flow
            for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
            if flow["context"]["source"] == SOURCE_REAUTH
        ]

        service.fetch_all_features.side_effect = PyViCareInvalidCredentialsError(
            "invalid_grant"
        )
        freezer.tick(timedelta(seconds=120))
        async_fire_time_changed(hass, fire_all=True)
        await hass.async_block_till_done(wait_background_tasks=True)

        reauth_flows = [
            flow
            for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
            if flow["context"]["source"] == SOURCE_REAUTH
        ]
        assert len(reauth_flows) == 1


async def test_setup_runs_pyvicare_init_and_fetches_once_per_gateway(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setup drives the real _setup_vicare_api path, not a prebuilt ViCareData.

    Mocks PyViCare at the API boundary so the via-gateway init, gateway-based
    cache reconfiguration, and single fetch per gateway are all exercised.
    """
    # Two devices behind gwA, one behind gwB: two gateways, three devices.
    fixtures: list[Fixture] = [
        Fixture({"type:climateSensor"}, "vicare/RoomSensor1.json", gateway="gwA"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor2.json", gateway="gwA"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor1.json", gateway="gwB"),
    ]
    client = MockPyViCare(fixtures)
    client.loadViaGateway = Mock()
    client.setCacheDuration = Mock()
    client.initWithExternalOAuth = Mock()

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=client),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # viaGateway mode enabled, cache duration scaled to the gateway count.
    client.loadViaGateway.assert_called_with(True)
    assert call(DEFAULT_CACHE_DURATION * 2) in client.setCacheDuration.call_args_list

    # First refresh fetches once per gateway representative, not once per device:
    # gwA fetches via devices[0], the sibling devices[1] never fetches.
    assert client.devices[0].service.fetch_all_features.call_count == 1
    assert client.devices[1].service.fetch_all_features.call_count == 0
    assert client.devices[2].service.fetch_all_features.call_count == 1
