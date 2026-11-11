"""Tests for the A Better Routeplanner integration setup."""

from dataclasses import replace
from http import HTTPStatus
from itertools import repeat
import time
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpVehicle,
    ConnectionEvent,
    ConnectionState,
    Telemetry,
    VehicleModelDisplay,
)
from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.abrp.const import ABRP_APP_KEY, DOMAIN, OAUTH2_TOKEN
from homeassistant.components.abrp.coordinator import GARAGE_SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL_2,
    MOCK_VEHICLE_NAME,
    MOCK_VEHICLE_NAME_2,
    SENSOR_TEST_SUB,
    build_metric_value,
    build_vehicle_model_display,
    fire_connection,
    fire_frame,
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
    ("status", "exc", "expected_state", "expected_reauth"),
    [
        pytest.param(
            HTTPStatus.UNAUTHORIZED,
            None,
            ConfigEntryState.SETUP_ERROR,
            True,
            id="rejected",
        ),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            None,
            ConfigEntryState.SETUP_RETRY,
            False,
            id="server_error",
        ),
        pytest.param(
            None,
            ClientError("boom"),
            ConfigEntryState.SETUP_RETRY,
            False,
            id="client_error",
        ),
        pytest.param(
            None,
            TimeoutError("boom"),
            ConfigEntryState.SETUP_RETRY,
            False,
            id="timeout",
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
    expected_reauth: bool,
) -> None:
    """A rejected refresh starts reauth; a 5xx, connection error or timeout retries."""
    config_entry.add_to_hass(hass)
    aioclient_mock.post(OAUTH2_TOKEN, status=status, exc=exc)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is expected_state
    assert (
        any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        is expected_reauth
    )


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
    ("status", "exc", "expected", "expected_reauth"),
    [
        pytest.param(HTTPStatus.BAD_REQUEST, None, AbrpAuthError, True, id="rejected"),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            None,
            AbrpApiError,
            False,
            id="server_error",
        ),
        pytest.param(None, ClientError("boom"), AbrpApiError, False, id="client_error"),
        pytest.param(None, TimeoutError(), AbrpApiError, False, id="timeout"),
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
    expected_reauth: bool,
) -> None:
    """Only a rejected refresh is terminal and starts reauth; others are API errors.

    The library stops on ``AbrpAuthError`` and backs off on anything else.
    """
    await setup_integration(hass, config_entry_with_vehicles)
    _expire_token(hass, config_entry_with_vehicles)
    aioclient_mock.post(OAUTH2_TOKEN, status=status, exc=exc)

    with pytest.raises(expected):
        await stream_auth(mock_telemetry_stream).async_get_access_token()
    await hass.async_block_till_done()

    assert (
        any(config_entry_with_vehicles.async_get_active_flows(hass, {SOURCE_REAUTH}))
        is expected_reauth
    )


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
    ("side_effect", "expected_state", "expected_reauth"),
    [
        pytest.param(
            AbrpAuthError("invalid session"),
            ConfigEntryState.SETUP_ERROR,
            True,
            id="auth_error",
        ),
        pytest.param(
            AbrpApiError("backend overloaded"),
            ConfigEntryState.SETUP_RETRY,
            False,
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
    expected_reauth: bool,
) -> None:
    """A garage-fetch auth error starts reauth; an API error retries."""
    config_entry.add_to_hass(hass)
    mock_abrp_client.side_effect = side_effect

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is expected_state
    assert (
        any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        is expected_reauth
    )


@pytest.mark.parametrize(
    ("side_effect", "expected_reauth"),
    [
        pytest.param(AbrpAuthError("HTTP 401"), True, id="auth_error"),
        pytest.param(AbrpApiError("HTTP 503"), False, id="api_error"),
    ],
)
@pytest.mark.usefixtures("mock_telemetry_stream")
async def test_garage_poll_failure(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
    expected_reauth: bool,
) -> None:
    """A poll-time auth error starts reauth; an API error waits for the next poll."""
    await setup_integration(hass, config_entry_with_vehicles)

    mock_abrp_client.side_effect = side_effect
    freezer.tick(GARAGE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry_with_vehicles.state is ConfigEntryState.LOADED
    assert (
        any(config_entry_with_vehicles.async_get_active_flows(hass, {SOURCE_REAUTH}))
        is expected_reauth
    )


@pytest.mark.usefixtures("mock_telemetry_stream")
async def test_devices_created_from_garage(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_abrp_vehicles: list[AbrpVehicle],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Each vehicle gets a device; without a name or display it shows the typecode."""
    display = build_vehicle_model_display()
    mock_abrp_client.return_value = [
        replace(mock_abrp_vehicles[0], display=display),
        replace(mock_abrp_vehicles[1], name=None),
    ]

    await setup_integration(hass, config_entry_with_vehicles)

    devices = [
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{config_entry_with_vehicles.unique_id}_{vehicle_id}"),
            config_entry_with_vehicles.entry_id,
        )
        for vehicle_id in (MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2)
    ]
    # ``model_name`` drops the make, which has its own field.
    assert [
        (device.name, device.manufacturer, device.model, device.configuration_url)
        for device in devices
    ] == [
        (
            MOCK_VEHICLE_NAME,
            display.manufacturer,
            display.model_name,
            f"https://abetterrouteplanner.com/?vehicle_id={MOCK_VEHICLE_ID}",
        ),
        (
            MOCK_VEHICLE_MODEL_2,
            None,
            MOCK_VEHICLE_MODEL_2,
            f"https://abetterrouteplanner.com/?vehicle_id={MOCK_VEHICLE_ID_2}",
        ),
    ]


_DISPLAY = build_vehicle_model_display()


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        pytest.param(
            _DISPLAY,
            (_DISPLAY.manufacturer, _DISPLAY.model_name),
            id="resolved_model_kept",
        ),
        pytest.param(None, (None, "new:typecode"), id="typecode_followed"),
    ],
)
@pytest.mark.usefixtures("mock_telemetry_stream")
async def test_display_missing_on_poll_keeps_device_metadata(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_abrp_vehicles: list[AbrpVehicle],
    device_registry: dr.DeviceRegistry,
    display: VehicleModelDisplay | None,
    expected: tuple[str | None, str],
) -> None:
    """A garage without display metadata keeps a resolved model, else the typecode."""
    mock_abrp_client.return_value = [replace(mock_abrp_vehicles[0], display=display)]
    await setup_integration(hass, config_entry_with_vehicles)

    mock_abrp_client.return_value = [
        replace(mock_abrp_vehicles[0], vehicle_model="new:typecode")
    ]
    # A reload, as after a vehicle is removed, runs the same sync as a poll.
    await hass.config_entries.async_reload(config_entry_with_vehicles.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry_with_vehicles.unique_id}_{MOCK_VEHICLE_ID}"),
        config_entry_with_vehicles.entry_id,
    )
    assert (device.manufacturer, device.model) == expected


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
        [],
        on_update=ANY,
        on_connection_change=ANY,
        name=config_entry_with_vehicles.title,
    )
    mock_telemetry_stream.return_value.set_vehicle_ids.assert_called_once_with(
        {MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2}
    )
    mock_telemetry_stream.return_value.start.assert_awaited_once()


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


@pytest.mark.parametrize(
    "initial_indexes",
    [
        pytest.param([0], id="vehicle_added"),
        pytest.param([], id="added_to_empty_garage"),
    ],
)
async def test_vehicle_added_to_garage_appears_without_reload(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_abrp_vehicles: list[AbrpVehicle],
    device_registry: dr.DeviceRegistry,
    mock_telemetry_stream: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    initial_indexes: list[int],
) -> None:
    """A vehicle added to the ABRP garage becomes a device on the next poll.

    The first vehicle also comes back renamed, which the poll carries over.
    """
    mock_abrp_client.return_value = [mock_abrp_vehicles[i] for i in initial_indexes]
    await setup_integration(hass, config_entry_with_vehicles)

    mock_telemetry_stream.return_value.set_vehicle_ids.reset_mock()
    polled = [replace(mock_abrp_vehicles[0], name="Weekend car"), mock_abrp_vehicles[1]]
    mock_abrp_client.return_value = polled
    freezer.tick(GARAGE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    scope = config_entry_with_vehicles.unique_id
    assert [
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{scope}_{raw.vehicle_id}"), config_entry_with_vehicles.entry_id
        ).name
        for raw in polled
    ] == ["Weekend car", MOCK_VEHICLE_NAME_2]
    # Not reloaded: the one stream is resubscribed in place.
    mock_telemetry_stream.assert_called_once()
    mock_telemetry_stream.return_value.set_vehicle_ids.assert_called_once_with(
        {MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2}
    )
    assert caplog.text.count(f"No display metadata for vehicle {MOCK_VEHICLE_ID}") == 1


_ONE = [
    AbrpVehicle(
        vehicle_id=MOCK_VEHICLE_ID, name=MOCK_VEHICLE_NAME, vehicle_model="model"
    )
]
_BOTH = [
    *_ONE,
    AbrpVehicle(
        vehicle_id=MOCK_VEHICLE_ID_2, name=MOCK_VEHICLE_NAME_2, vehicle_model="model"
    ),
]
_FAILED = AbrpApiError("HTTP 503")


@pytest.mark.parametrize(
    ("polls", "kept", "streamed"),
    [
        pytest.param([_ONE], False, False, id="missing"),
        pytest.param([_ONE, _BOTH], True, True, id="back_after_removal"),
        pytest.param([[]], True, False, id="empty_garage"),
    ],
)
async def test_vehicle_leaving_garage(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    mock_telemetry_stream: MagicMock,
    freezer: FrozenDateTimeFactory,
    polls: list[list[AbrpVehicle] | Exception],
    kept: bool,
    streamed: bool,
) -> None:
    """A vehicle missing from a garage fetch loses its device and entities."""
    frame = Telemetry(voltage=build_metric_value(400.0))
    await setup_integration(hass, config_entry_with_vehicles)
    # Another account's device must never be swept up.
    other_entry = MockConfigEntry(domain=DOMAIN, unique_id="other-sub")
    other_entry.add_to_hass(hass)
    other = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, f"other-sub_{MOCK_VEHICLE_ID_2}")},
    )
    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID_2, frame)
    await hass.async_block_till_done()

    for poll in polls:
        # Repeated, so a reload's setup fetch gets the same garage.
        mock_abrp_client.side_effect = repeat(poll)
        freezer.tick(GARAGE_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    # A reload after a removal starts without telemetry.
    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID_2, frame)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID_2}"),
        config_entry_with_vehicles.entry_id,
    )
    assert (device is not None) is kept
    assert (
        hass.states.get("sensor.rivian_r1s_2024_quad_max_voltage") is not None
    ) is kept
    assert device_registry.async_get(other.id) is not None
    stream_ids = mock_telemetry_stream.return_value.set_vehicle_ids.call_args.args[0]
    assert (MOCK_VEHICLE_ID_2 in stream_ids) is streamed


@pytest.mark.parametrize(
    ("garage", "vehicle_id", "removable", "streams"),
    [
        pytest.param(_ONE, MOCK_VEHICLE_ID, False, 1, id="in_garage"),
        pytest.param(_ONE, MOCK_VEHICLE_ID_2, True, 2, id="left_garage"),
        pytest.param(_FAILED, MOCK_VEHICLE_ID, True, 0, id="not_loaded"),
    ],
)
async def test_remove_device(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    mock_telemetry_stream: MagicMock,
    hass_ws_client: WebSocketGenerator,
    garage: list[AbrpVehicle] | Exception,
    vehicle_id: int,
    removable: bool,
    streams: int,
) -> None:
    """Only a device whose vehicle has left the garage can be deleted by hand."""
    assert await async_setup_component(hass, "config", {})
    mock_abrp_client.side_effect = repeat(garage)
    config_entry_with_vehicles.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_vehicles.entry_id)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry_with_vehicles.entry_id,
        identifiers={(DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}")},
    )

    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    await hass.async_block_till_done()

    assert response["success"] is removable
    assert (device_registry.async_get(device.id) is None) is removable
    # Deleting from a loaded entry reloads it, which starts a second stream.
    assert mock_telemetry_stream.call_count == streams
