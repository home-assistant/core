"""Tests for the A Better Routeplanner integration setup."""

from http import HTTPStatus
import logging
import time
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpVehicle,
    ConnectionEvent,
    ConnectionState,
)
from aiohttp import ClientError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.abrp.const import ABRP_APP_KEY, DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestTransientError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration
from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_MODEL_2,
    build_vehicle_model_display,
    fire_connection,
    stream_auth,
)


@pytest.mark.usefixtures("mock_abrp_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Setup loads the entry; unload stops the stream once the platforms unload."""
    await setup_integration(hass, config_entry_with_vehicles)

    assert config_entry_with_vehicles.state is ConfigEntryState.LOADED
    mock_telemetry_stream.return_value.stop.assert_not_awaited()

    assert await hass.config_entries.async_unload(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.NOT_LOADED
    mock_telemetry_stream.return_value.stop.assert_awaited_once()

    # The shutdown listener must go with the entry.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_telemetry_stream.return_value.stop.assert_awaited_once()


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
async def test_setup_token_refresh_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An expired token is refreshed during setup."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data["token"]["access_token"] == "updated-access-token"
    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize(
    ("status", "exc", "expected_state"),
    [
        pytest.param(
            HTTPStatus.UNAUTHORIZED, None, ConfigEntryState.SETUP_ERROR, id="rejected"
        ),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            None,
            ConfigEntryState.SETUP_RETRY,
            id="server_error",
        ),
        pytest.param(
            None, ClientError("boom"), ConfigEntryState.SETUP_RETRY, id="client_error"
        ),
        pytest.param(
            None, TimeoutError("boom"), ConfigEntryState.SETUP_RETRY, id="timeout"
        ),
    ],
)
@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_setup_token_refresh_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus | None,
    exc: Exception | None,
    expected_state: ConfigEntryState,
) -> None:
    """A rejected refresh fails setup; a 5xx, connection error or timeout retries."""
    config_entry.add_to_hass(hass)
    aioclient_mock.post(OAUTH2_TOKEN, status=status, exc=exc)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is expected_state


def _expire_token(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Mark the stored token as expired so the next use refreshes it."""
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "token": {**entry.data["token"], "expires_at": 0}},
    )


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_auth_refreshes_expired_token(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The stream gets a refreshed token once the stored one expires."""
    await setup_integration(hass, config_entry_with_vehicles)
    _expire_token(hass, config_entry_with_vehicles)
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "refreshed-access-token",
            "refresh_token": "refreshed-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    token = await stream_auth(mock_telemetry_stream).async_get_access_token()

    assert token == "refreshed-access-token"
    assert (
        config_entry_with_vehicles.data["token"]["access_token"]
        == "refreshed-access-token"
    )


@pytest.mark.parametrize(
    ("status", "exc", "expected"),
    [
        pytest.param(HTTPStatus.BAD_REQUEST, None, AbrpAuthError, id="rejected"),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            None,
            OAuth2TokenRequestTransientError,
            id="server_error",
        ),
        pytest.param(None, ClientError("boom"), ClientError, id="client_error"),
        pytest.param(None, TimeoutError(), TimeoutError, id="timeout"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_auth_refresh_failure(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus | None,
    exc: Exception | None,
    expected: type[Exception],
) -> None:
    """Only a rejected refresh is terminal for the stream.

    The library stops on ``AbrpAuthError`` and backs off on anything else.
    """
    await setup_integration(hass, config_entry_with_vehicles)
    _expire_token(hass, config_entry_with_vehicles)
    aioclient_mock.post(OAUTH2_TOKEN, status=status, exc=exc)

    with pytest.raises(expected):
        await stream_auth(mock_telemetry_stream).async_get_access_token()


async def test_setup_missing_implementation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """A missing OAuth2 implementation surfaces as SETUP_RETRY."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.abrp.config_entry_oauth2_flow"
        ".async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            AbrpAuthError("invalid session"),
            ConfigEntryState.SETUP_ERROR,
            id="auth_error",
        ),
        pytest.param(
            AbrpApiError("backend overloaded"),
            ConfigEntryState.SETUP_RETRY,
            id="api_error",
        ),
    ],
)
async def test_garage_fetch_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """A garage-fetch auth error fails setup; an API error retries."""
    config_entry.add_to_hass(hass)
    mock_abrp_client.side_effect = side_effect

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is expected_state


@pytest.mark.parametrize(
    ("display_error", "warns"),
    [
        pytest.param(AbrpAuthError("HTTP 401"), True, id="auth_error"),
        pytest.param(ValueError("boom"), True, id="unexpected_error"),
        pytest.param(AbrpApiError("HTTP 404"), False, id="api_error"),
        pytest.param(TimeoutError("budget exceeded"), False, id="timeout"),
    ],
)
@pytest.mark.usefixtures("mock_telemetry_stream")
async def test_display_failure_degrades_only_that_vehicle(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    display_error: Exception,
    warns: bool,
) -> None:
    """A failed display lookup falls back for that vehicle only.

    Rejections and unexpected errors warn; a 404 or timeout is routine.
    """
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = display_error
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL_2] = (
        build_vehicle_model_display(manufacturer="Rivian", model="R1S")
    )

    await setup_integration(hass, config_entry_with_vehicles)

    assert f"No display metadata for vehicle {MOCK_VEHICLE_ID}" in caplog.text
    scope = config_entry_with_vehicles.unique_id
    degraded = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{scope}_{MOCK_VEHICLE_ID}"), config_entry_with_vehicles.entry_id
    )
    enriched = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{scope}_{MOCK_VEHICLE_ID_2}"), config_entry_with_vehicles.entry_id
    )
    assert degraded.manufacturer is None
    assert degraded.model == MOCK_VEHICLE_MODEL
    assert enriched.manufacturer == "Rivian"
    assert (
        any(
            record.levelno == logging.WARNING and MOCK_VEHICLE_MODEL in record.message
            for record in caplog.records
        )
        is warns
    )


@pytest.mark.usefixtures("mock_abrp_client")
async def test_connection_logged_once_per_transition(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Repeated identical connection states log only on the transition."""
    await setup_integration(hass, config_entry_with_vehicles)

    for reason in ("first", "second"):
        fire_connection(
            mock_telemetry_stream,
            ConnectionEvent(ConnectionState.DISCONNECTED, reason),
        )
    fire_connection(mock_telemetry_stream, ConnectionEvent(ConnectionState.CONNECTED))

    assert caplog.text.count("stream disconnected") == 1
    assert caplog.text.count("stream connected") == 1


@pytest.mark.parametrize(
    "garage_indexes",
    [
        pytest.param([0, 1], id="two_vehicles"),
        pytest.param([0, 1, 0], id="duplicate_vehicle"),
    ],
)
async def test_stream_spawned_for_every_garage_vehicle(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_abrp_vehicles: list[AbrpVehicle],
    mock_telemetry_stream: MagicMock,
    garage_indexes: list[int],
) -> None:
    """Setup subscribes the stream to every garage vehicle, each once."""
    mock_abrp_client.return_value = [mock_abrp_vehicles[i] for i in garage_indexes]

    await setup_integration(hass, config_entry_with_vehicles)

    mock_telemetry_stream.assert_called_once_with(
        ANY,
        ABRP_APP_KEY,
        ANY,
        [MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2],
        on_update=ANY,
        on_connection_change=ANY,
        name=config_entry_with_vehicles.title,
    )
    mock_telemetry_stream.return_value.start.assert_awaited_once()


async def test_no_stream_when_garage_is_empty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """An empty garage loads the entry with no stream, devices or entities."""
    mock_abrp_client.return_value = []

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    mock_telemetry_stream.assert_not_called()
    assert not dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)


@pytest.mark.usefixtures("mock_abrp_client")
async def test_shutdown_stops_stream(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Home Assistant stopping stops the stream without unloading the entry."""
    await setup_integration(hass, config_entry_with_vehicles)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_telemetry_stream.return_value.stop.assert_awaited_once()


async def test_vehicle_added_to_garage_appears_after_reload(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_abrp_vehicles: list[AbrpVehicle],
    device_registry: dr.DeviceRegistry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """A vehicle added to the ABRP garage becomes a device on the next reload."""
    mock_abrp_client.return_value = mock_abrp_vehicles[:1]
    await setup_integration(hass, config_entry_with_vehicles)

    scope = config_entry_with_vehicles.unique_id
    identifier = (DOMAIN, f"{scope}_{MOCK_VEHICLE_ID_2}")
    assert (
        device_registry.async_get_device_by_identifier(
            identifier, config_entry_with_vehicles.entry_id
        )
        is None
    )

    mock_abrp_client.return_value = mock_abrp_vehicles
    await hass.config_entries.async_reload(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            identifier, config_entry_with_vehicles.entry_id
        )
        is not None
    )
    mock_telemetry_stream.assert_called_with(
        ANY,
        ANY,
        ANY,
        [MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2],
        on_update=ANY,
        on_connection_change=ANY,
        name=ANY,
    )
