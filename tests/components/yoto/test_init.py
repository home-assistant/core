"""Tests for the Yoto integration setup."""

from unittest.mock import MagicMock, Mock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from yoto_api import YotoAPIError, YotoError

from homeassistant.components.yoto.const import (
    DOMAIN,
    SCAN_INTERVAL,
    STATUS_PUSH_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestError
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("setup_credentials")


async def test_setup_unload(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The integration loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_yoto_client.disconnect_events.assert_called_once()


async def test_setup_retries_on_api_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A non-auth API failure surfaces as a setup retry."""
    mock_yoto_client.refresh.side_effect = YotoAPIError("boom")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mqtt_event_updates_entity(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An MQTT event published by the broker refreshes the entity state."""
    await setup_integration(hass, mock_config_entry)
    state_before = hass.states.get("media_player.nursery_yoto")
    assert state_before is not None

    # connect_events(device_ids, on_update) — invoke the registered on_update callback
    on_update = mock_yoto_client.connect_events.call_args.args[1]
    player = next(iter(mock_yoto_client.players.values()))
    player.last_event.volume = 12
    on_update(player)
    await hass.async_block_till_done()

    state_after = hass.states.get("media_player.nursery_yoto")
    assert state_after is not None
    assert state_after.attributes["volume_level"] == 12 / 16
    assert state_after.last_updated > state_before.last_updated


async def test_status_push_tick(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The status-push timer publishes a request every 60 s."""
    mock_yoto_client.is_mqtt_connected = True
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.request_status_push.reset_mock()

    freezer.tick(STATUS_PUSH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_yoto_client.request_status_push.assert_called_once_with("player-test")


async def test_status_push_skipped_when_mqtt_disconnected(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The status-push timer is a no-op while MQTT is reconnecting."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.request_status_push.reset_mock()
    mock_yoto_client.is_mqtt_connected = False

    freezer.tick(STATUS_PUSH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_yoto_client.request_status_push.assert_not_called()


async def test_periodic_poll_refreshes_players(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The coordinator refreshes the player list on every tick."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.refresh.reset_mock()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_yoto_client.refresh.assert_called_once()


async def test_setup_retries_when_implementation_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Missing OAuth2 implementation defers setup as not-ready."""
    with patch(
        "homeassistant.components.yoto.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError("gone"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [
        aiohttp.ClientError("boom"),
        OAuth2TokenRequestError(request_info=Mock(), domain=DOMAIN),
    ],
)
async def test_setup_retries_on_token_validation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """A failure refreshing the OAuth token defers setup."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=side_effect,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_mqtt_unavailable(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """MQTT connect failure surfaces as a setup retry."""
    mock_yoto_client.connect_events.side_effect = YotoError("mqtt down")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_succeeds_without_card_library(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A library load failure doesn't block setup; titles and artwork stay empty."""
    mock_yoto_client.update_library.side_effect = YotoError("library down")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        aiohttp.ClientError("boom"),
        OAuth2TokenRequestError(request_info=Mock(), domain=DOMAIN),
    ],
)
@pytest.mark.usefixtures("mock_yoto_client")
async def test_periodic_poll_fails_on_token_validation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """A failure refreshing the OAuth token marks the coordinator failed."""
    await setup_integration(hass, mock_config_entry)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=side_effect,
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is False


async def test_periodic_poll_fails_on_api_error(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A non-auth API error during periodic refresh marks the coordinator failed."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.refresh.side_effect = YotoAPIError("boom")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is False
