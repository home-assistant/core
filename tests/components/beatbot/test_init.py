"""Tests for Beatbot config entry setup, polling and event handling."""

import asyncio
from datetime import timedelta
import time
from unittest.mock import AsyncMock, MagicMock

from beatbot_cloud import (
    BeatbotAuthenticationError,
    BeatbotConnectionError,
    BeatbotDeviceData,
    BeatbotEvent,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.beatbot.const import DOMAIN, NETWORK_REFRESH_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    BATTERY_ENTITY_ID,
    DEVICE_ID,
    INTERFACE_BATTERY,
    INTERFACE_STATE,
    STATUS_ENTITY_ID,
    TOKEN_URL,
    batch_state,
    create_device,
    library_callback,
    property_change,
    setup_integration,
    status_event,
    topology_event,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

NEW_DEVICE_ID = "pool-cleaner-2"
NEW_STATUS_ENTITY_ID = "sensor.aquasense_2_pro_status"

REFRESHED_TOKEN = {
    "access_token": "new-access-token",
    "refresh_token": "new-refresh-token",
    "token_type": "bearer",
    "expires_in": 3600,
}


async def poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance to the next reconciliation poll and let it finish."""
    freezer.tick(timedelta(seconds=NETWORK_REFRESH_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
) -> None:
    """Set up the entry, load entities, then stop the event stream on unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(STATUS_ENTITY_ID) is not None
    assert set(mock_event_client.call_args.kwargs) == {
        "state_callback",
        "device_added_callback",
        "reconnect_callback",
        "token_refresh_callback",
    }
    assert mock_event_client.return_value.async_run.await_count == 1

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    # The registry keeps the entity, but no live platform provides it anymore.
    state = hass.states.get(STATUS_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    mock_event_client.return_value.async_close.assert_awaited_once()


@pytest.mark.parametrize(
    ("method", "error", "expected_state"),
    [
        pytest.param(
            "get_devices",
            BeatbotAuthenticationError(),
            ConfigEntryState.SETUP_ERROR,
            id="discovery-authentication",
        ),
        pytest.param(
            "get_devices",
            BeatbotConnectionError("offline"),
            ConfigEntryState.SETUP_RETRY,
            id="discovery-connection",
        ),
        pytest.param(
            "get_device_states",
            BeatbotAuthenticationError(),
            ConfigEntryState.SETUP_ERROR,
            id="state-authentication",
        ),
        pytest.param(
            "get_device_states",
            BeatbotConnectionError("offline"),
            ConfigEntryState.SETUP_RETRY,
            id="state-connection",
        ),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    method: str,
    error: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Retry transient failures and fail setup when the credentials are rejected."""
    getattr(mock_client, method).side_effect = error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    mock_event_client.assert_not_called()


async def test_poll_applies_batch_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Apply the batched device state on the reconciliation poll."""
    assert hass.states.get(BATTERY_ENTITY_ID).state == "80"

    mock_client.get_device_states.return_value = batch_state(
        states={INTERFACE_BATTERY: 42}
    )
    await poll(hass, freezer)

    assert hass.states.get(BATTERY_ENTITY_ID).state == "42"


async def test_poll_partial_batch_keeps_discovery_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep the discovery values a partial batch response does not report."""
    mock_client.get_device_states.return_value = batch_state(
        states={INTERFACE_STATE: 2}
    )
    await poll(hass, freezer)

    assert hass.states.get(STATUS_ENTITY_ID).state == "charging"
    assert hass.states.get(BATTERY_ENTITY_ID).state == "80"


@pytest.mark.parametrize("method", ["get_devices", "get_device_states"])
@pytest.mark.usefixtures("init_integration")
async def test_poll_preserves_concurrent_push(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    method: str,
) -> None:
    """Preserve push events received while either REST request is pending."""
    started = asyncio.Event()
    release = asyncio.Event()
    mock_client.get_devices.return_value = [create_device()]
    response = getattr(mock_client, method).return_value

    async def delayed_response() -> object:
        started.set()
        await release.wait()
        return response

    getattr(mock_client, method).side_effect = delayed_response
    refresh = hass.async_create_task(
        library_callback(mock_event_client, "reconnect_callback")()
    )
    await started.wait()
    state_callback = library_callback(mock_event_client, "state_callback")
    state_callback(property_change(INTERFACE_BATTERY, 42))
    state_callback(property_change(INTERFACE_BATTERY, 43))
    release.set()
    await refresh
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "43"


@pytest.mark.usefixtures("init_integration")
async def test_failed_poll_does_not_replay_push_on_next_poll(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Discard the pending event buffer when a refresh fails."""

    async def failed_response() -> None:
        library_callback(mock_event_client, "state_callback")(
            property_change(INTERFACE_BATTERY, 42)
        )
        raise BeatbotConnectionError("offline")

    mock_client.get_device_states.side_effect = failed_response
    await poll(hass, freezer)
    assert hass.states.get(BATTERY_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_client.get_devices.return_value = [create_device()]
    mock_client.get_device_states.side_effect = None
    mock_client.get_device_states.return_value = batch_state(
        states={INTERFACE_BATTERY: 60}
    )
    await poll(hass, freezer)

    assert hass.states.get(BATTERY_ENTITY_ID).state == "60"


async def test_poll_discovers_added_device(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Load platforms for a device that shows up in a later poll."""
    assert hass.states.get(NEW_STATUS_ENTITY_ID) is None

    mock_client.get_devices.return_value = [
        create_device(),
        create_device(NEW_DEVICE_ID, name="AquaSense 2 Pro"),
    ]
    await poll(hass, freezer)

    assert hass.states.get(NEW_STATUS_ENTITY_ID) is not None


async def test_poll_keeps_missing_device_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep a device that vanished from discovery, but stop reporting it as current."""
    mock_client.get_devices.return_value = []
    await poll(hass, freezer)

    assert hass.states.get(STATUS_ENTITY_ID).state == STATE_UNAVAILABLE
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, DEVICE_ID), init_integration.entry_id
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{DEVICE_ID}_status"
        )
        is not None
    )


async def test_state_event_updates_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_event_client: MagicMock,
) -> None:
    """Overlay a pushed property change on the coordinator data."""
    library_callback(mock_event_client, "state_callback")(
        property_change(INTERFACE_BATTERY, 42)
    )
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "42"


@pytest.mark.freeze_time
async def test_state_event_does_not_reset_poll(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep the reconciliation poll on schedule despite steady event traffic."""
    assert mock_client.get_devices.call_count == 1

    library_callback(mock_event_client, "state_callback")(
        property_change(INTERFACE_BATTERY, 42)
    )
    await hass.async_block_till_done()

    assert mock_client.get_devices.call_count == 1

    await poll(hass, freezer)

    assert mock_client.get_devices.call_count == 2


async def test_status_event_marks_device_offline(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_event_client: MagicMock,
) -> None:
    """Stop reporting state when the device pushes an offline status."""
    library_callback(mock_event_client, "state_callback")(status_event(False))
    await hass.async_block_till_done()

    assert hass.states.get(STATUS_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(topology_event(), id="device-set-event"),
        pytest.param(
            property_change(INTERFACE_BATTERY, 42, "unknown-device"),
            id="unknown-device",
        ),
    ],
)
async def test_unroutable_event_is_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_event_client: MagicMock,
    event: BeatbotEvent,
) -> None:
    """Ignore events that carry no state for a known device."""
    library_callback(mock_event_client, "state_callback")(event)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "80"


async def test_device_added_event_reloads_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
) -> None:
    """Load platforms when the event stream reports a new device."""
    assert hass.states.get(NEW_STATUS_ENTITY_ID) is None
    assert mock_client.get_devices.call_count == 1

    mock_client.get_devices.return_value = [
        create_device(),
        create_device(NEW_DEVICE_ID, name="AquaSense 2 Pro"),
    ]
    # Both arrive before the scheduled reload runs, so only one is acted on.
    device_added = library_callback(mock_event_client, "device_added_callback")
    device_added(NEW_DEVICE_ID)
    device_added(NEW_DEVICE_ID)
    await hass.async_block_till_done()

    assert hass.states.get(NEW_STATUS_ENTITY_ID) is not None
    assert mock_client.get_devices.call_count == 2


@pytest.mark.parametrize(
    ("response", "expected_state"),
    [
        pytest.param([create_device()], "80", id="rest-available"),
        pytest.param(BeatbotAuthenticationError(), STATE_UNAVAILABLE, id="rest-auth"),
        pytest.param(BeatbotConnectionError(), STATE_UNAVAILABLE, id="rest-connection"),
    ],
)
async def test_event_stream_stops_on_token_rejection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    response: list[BeatbotDeviceData] | Exception,
    expected_state: str,
) -> None:
    """Validate REST availability after the event stream rejects the token."""
    mock_client.get_devices.side_effect = [[create_device()], response]
    mock_event_client.return_value.async_run = AsyncMock(
        side_effect=BeatbotAuthenticationError()
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "Beatbot event stream authorization failed" in caplog.text
    assert mock_client.get_devices.await_count == 2
    assert hass.states.get(BATTERY_ENTITY_ID).state == expected_state
    assert not hass.config_entries.flow.async_progress()


async def test_expired_token_is_refreshed_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client_class: MagicMock,
    mock_event_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Refresh an expired token for the library instead of asking the user again."""
    mock_config_entry.data["token"]["expires_at"] = time.time() - 10
    aioclient_mock.post(TOKEN_URL, json=REFRESHED_TOKEN)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    access_token = mock_client_class.call_args.args[2]

    assert await access_token() == "new-access-token"
    assert mock_config_entry.data["token"]["access_token"] == "new-access-token"
    assert len(aioclient_mock.mock_calls) == 1

    # The refreshed token is reused instead of hitting the token endpoint again.
    assert await access_token() == "new-access-token"
    assert len(aioclient_mock.mock_calls) == 1


async def test_rejected_refresh_token_is_translated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client_class: MagicMock,
    mock_event_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Translate an OAuth refresh rejection into a library authentication error."""
    mock_config_entry.data["token"]["expires_at"] = time.time() - 10
    aioclient_mock.post(TOKEN_URL, status=400)

    await setup_integration(hass, mock_config_entry)

    access_token = mock_client_class.call_args.args[2]
    with pytest.raises(BeatbotAuthenticationError):
        await access_token()


async def test_transient_refresh_failure_stays_retryable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client_class: MagicMock,
    mock_event_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Keep a token endpoint outage retryable instead of asking for reauth."""
    mock_config_entry.data["token"]["expires_at"] = time.time() - 10
    aioclient_mock.post(TOKEN_URL, status=500)

    await setup_integration(hass, mock_config_entry)

    access_token = mock_client_class.call_args.args[2]
    with pytest.raises(BeatbotConnectionError):
        await access_token()


async def test_event_stream_refreshes_rejected_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Refresh a token the event stream rejected and return the replacement."""
    aioclient_mock.post(TOKEN_URL, json=REFRESHED_TOKEN)

    await setup_integration(hass, mock_config_entry)
    refresh_token = library_callback(mock_event_client, "token_refresh_callback")

    assert await refresh_token("access-token") == "new-access-token"
    assert mock_config_entry.data["token"]["access_token"] == "new-access-token"
    assert len(aioclient_mock.mock_calls) == 1


async def test_event_stream_ignores_stale_token_rejection(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Reuse the current token when a superseded one is rejected."""
    refresh_token = library_callback(mock_event_client, "token_refresh_callback")

    assert await refresh_token("superseded-token") == "access-token"
    assert len(aioclient_mock.mock_calls) == 0


async def test_event_stream_translates_rejected_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Translate an OAuth refresh rejection for the event stream."""
    aioclient_mock.post(TOKEN_URL, status=400)
    refresh_token = library_callback(mock_event_client, "token_refresh_callback")

    with pytest.raises(BeatbotAuthenticationError):
        await refresh_token("access-token")


async def test_event_stream_keeps_transient_refresh_failure_retryable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Keep a token endpoint outage on the event stream's reconnect path."""
    aioclient_mock.post(TOKEN_URL, status=500)
    refresh_token = library_callback(mock_event_client, "token_refresh_callback")

    with pytest.raises(BeatbotConnectionError):
        await refresh_token("access-token")
