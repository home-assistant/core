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

from homeassistant.components.abetterrouteplanner.const import (
    ABRP_APP_KEY,
    DOMAIN,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestTransientError
from homeassistant.helpers import device_registry as dr
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

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Setup with a fresh token loads the entry; unload returns it to NOT_LOADED."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
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


@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
async def test_reload_restores_deleted_credential(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Deleting the built-in credential in the UI does not break a reload."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "application_credentials/delete",
            "application_credentials_id": "abetterrouteplanner_ha_abrp_integration",
        }
    )
    assert (await client.receive_json())["success"]

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


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
    """Only a rejected refresh is terminal for the stream; the rest are retried.

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
        "homeassistant.components.abetterrouteplanner.config_entry_oauth2_flow"
        ".async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


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


@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, scope), config_entry_with_vehicles.entry_id
    )
    assert device is not None
    assert device.model == MOCK_VEHICLE_MODEL
    assert device.manufacturer is None

    assert any(
        record.levelno == logging.INFO
        and str(MOCK_VEHICLE_ID) in record.message
        and MOCK_VEHICLE_MODEL in record.message
        for record in caplog.records
    )


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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_spawned_for_every_garage_vehicle(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Setup spawns the telemetry stream covering the whole garage."""
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.LOADED

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
) -> None:
    """An account whose garage is empty spawns NO telemetry stream."""
    mock_abrp_client.return_value = []
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    mock_telemetry_stream.assert_not_called()


@pytest.mark.usefixtures("mock_abrp_client")
async def test_unload_stops_stream(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Unloading an entry with a live stream stops it once the platforms unload."""
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    mock_telemetry_stream.return_value.stop.assert_not_awaited()

    assert await hass.config_entries.async_unload(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.NOT_LOADED
    mock_telemetry_stream.return_value.stop.assert_awaited_once()

    # The shutdown listener must go with the entry.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_telemetry_stream.return_value.stop.assert_awaited_once()


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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_survives_a_failed_platform_unload(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """The stream outlives an unload that left the entry's platforms loaded."""
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(
            config_entry_with_vehicles.entry_id
        )
        await hass.async_block_till_done()

    assert config_entry_with_vehicles.state is ConfigEntryState.FAILED_UNLOAD
    mock_telemetry_stream.return_value.stop.assert_not_awaited()


@pytest.mark.usefixtures("mock_abrp_client")
async def test_duplicate_garage_entry_yields_one_stream_id(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_abrp_vehicles: list[AbrpVehicle],
    mock_telemetry_stream: MagicMock,
) -> None:
    """A garage that repeats a vehicle subscribes that id only once."""
    mock_abrp_client.return_value = [*mock_abrp_vehicles, mock_abrp_vehicles[0]]
    config_entry_with_vehicles.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    mock_telemetry_stream.assert_called_with(
        ANY,
        ANY,
        ANY,
        [MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2],
        on_update=ANY,
        on_connection_change=ANY,
        name=ANY,
    )


@pytest.mark.usefixtures("mock_abrp_client")
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
    config_entry_with_vehicles.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

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
