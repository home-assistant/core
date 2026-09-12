"""Tests for PlayStation Network."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from psnawp_api.core import (
    PSNAWPAuthenticationError,
    PSNAWPClientError,
    PSNAWPForbiddenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
)
import pytest

from homeassistant.components.playstation_network.const import (
    CONF_NPSSO,
    CONF_TOKEN_RESPONSE,
    DOMAIN,
)
from homeassistant.components.playstation_network.coordinator import (
    PlaystationNetworkRuntimeData,
)
from homeassistant.components.playstation_network.helpers import PlaystationNetworkData
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import NPSSO_TOKEN, PSN_ID, TOKEN_RESPONSE

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_persists_token_response_for_existing_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test a token response is persisted for an existing config entry."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.data == {
        CONF_NPSSO: NPSSO_TOKEN,
        CONF_TOKEN_RESPONSE: TOKEN_RESPONSE,
    }


async def test_restores_and_persists_token_response(
    hass: HomeAssistant,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test stored tokens are restored and refreshed tokens are persisted."""
    stored_token_response = TOKEN_RESPONSE | {"access_token": "stored-access-token"}
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="test-user",
        data={
            CONF_NPSSO: NPSSO_TOKEN,
            CONF_TOKEN_RESPONSE: stored_token_response,
        },
        unique_id=PSN_ID,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_psnawpapi.authenticator.token_response == stored_token_response

    refreshed_token_response = TOKEN_RESPONSE | {
        "access_token": "refreshed-access-token",
        "refresh_token": "refreshed-refresh-token",
    }
    mock_psnawpapi.authenticator.token_response = refreshed_token_response

    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock()
    ) as async_reload:
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert config_entry.data[CONF_TOKEN_RESPONSE] == refreshed_token_response
    async_reload.assert_not_awaited()


async def test_reloads_after_reauth_with_unchanged_npsso(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test reauthentication reloads when only the token response changes."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    reauthenticated_token_response = TOKEN_RESPONSE | {
        "access_token": "reauthenticated-access-token",
        "refresh_token": "reauthenticated-refresh-token",
    }

    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock()
    ) as async_reload:
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                CONF_NPSSO: NPSSO_TOKEN,
                CONF_TOKEN_RESPONSE: reauthenticated_token_response,
            },
        )
        await hass.async_block_till_done()

    async_reload.assert_awaited_once_with(config_entry.entry_id)


async def test_reloads_after_friend_subentry_change(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test changing friend subentries reloads the integration."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock()
    ) as async_reload:
        hass.config_entries.async_remove_subentry(config_entry, "ABCDEF")
        await hass.async_block_till_done()

    async_reload.assert_awaited_once_with(config_entry.entry_id)


async def test_does_not_persist_tokens_from_client_replaced_by_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an old runtime client cannot overwrite reauthenticated tokens."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    stale_token_response = TOKEN_RESPONSE | {
        "access_token": "stale-access-token",
        "refresh_token": "stale-refresh-token",
    }
    reauthenticated_token_response = TOKEN_RESPONSE | {
        "access_token": "reauthenticated-access-token",
        "refresh_token": "reauthenticated-refresh-token",
    }
    mock_psnawpapi.authenticator.token_response = stale_token_response
    update_started = asyncio.Event()
    continue_update = asyncio.Event()

    async def delayed_get_data() -> PlaystationNetworkData:
        update_started.set()
        await continue_update.wait()
        return PlaystationNetworkData()

    with (
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()),
        patch(
            "homeassistant.components.playstation_network.helpers."
            "PlaystationNetwork.get_data",
            side_effect=delayed_get_data,
        ),
    ):
        # Trigger the scheduled refresh while the data fetch is held in flight.
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await update_started.wait()
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                CONF_NPSSO: NPSSO_TOKEN,
                CONF_TOKEN_RESPONSE: reauthenticated_token_response,
            },
        )
        continue_update.set()
        await hass.async_block_till_done()

    assert config_entry.data == {
        CONF_NPSSO: NPSSO_TOKEN,
        CONF_TOKEN_RESPONSE: reauthenticated_token_response,
    }


async def test_does_not_persist_tokens_when_reauth_precedes_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an old client cannot overwrite a completed same-NPSSO reauth."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    stale_token_response = TOKEN_RESPONSE | {
        "access_token": "stale-access-token",
        "refresh_token": "stale-refresh-token",
    }
    reauthenticated_token_response = TOKEN_RESPONSE | {
        "access_token": "reauthenticated-access-token",
        "refresh_token": "reauthenticated-refresh-token",
    }
    mock_psnawpapi.authenticator.token_response = stale_token_response

    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()):
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                CONF_NPSSO: NPSSO_TOKEN,
                CONF_TOKEN_RESPONSE: reauthenticated_token_response,
            },
        )
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert config_entry.data == {
        CONF_NPSSO: NPSSO_TOKEN,
        CONF_TOKEN_RESPONSE: reauthenticated_token_response,
    }


@pytest.mark.parametrize(
    "exception", [PSNAWPNotFoundError, PSNAWPServerError, PSNAWPClientError]
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
) -> None:
    """Test config entry not ready."""

    mock_psnawpapi.user.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test config entry auth failed setup error."""

    mock_psnawpapi.user.side_effect = PSNAWPAuthenticationError("error msg")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


@pytest.mark.parametrize(
    "exception", [PSNAWPNotFoundError, PSNAWPServerError, PSNAWPClientError]
)
async def test_coordinator_update_data_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
) -> None:
    """Test coordinator data update failed."""

    mock_psnawpapi.user.return_value.get_presence.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_persists_refreshed_token_when_coordinator_update_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a refreshed token is persisted when the data update fails."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    refreshed_token_response = TOKEN_RESPONSE | {
        "access_token": "refreshed-access-token",
        "refresh_token": "refreshed-refresh-token",
    }

    def refresh_token_then_fail() -> None:
        mock_psnawpapi.authenticator.token_response = refreshed_token_response
        raise PSNAWPServerError("error msg")

    mock_psnawpapi.user.return_value.get_presence.side_effect = refresh_token_then_fail

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.data[CONF_TOKEN_RESPONSE] == refreshed_token_response


async def test_persists_refreshed_token_when_setup_fails(
    hass: HomeAssistant,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test a refreshed token is persisted when setup fails."""
    stored_token_response = TOKEN_RESPONSE | {"access_token": "stored-access-token"}
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="test-user",
        data={
            CONF_NPSSO: NPSSO_TOKEN,
            CONF_TOKEN_RESPONSE: stored_token_response,
        },
        unique_id=PSN_ID,
    )
    refreshed_token_response = TOKEN_RESPONSE | {
        "access_token": "refreshed-access-token",
        "refresh_token": "refreshed-refresh-token",
    }

    def refresh_token_then_fail() -> None:
        mock_psnawpapi.authenticator.token_response = refreshed_token_response
        raise PSNAWPServerError("error msg")

    mock_psnawpapi.me.return_value.get_shareable_profile_link.side_effect = (
        refresh_token_then_fail
    )
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.data[CONF_TOKEN_RESPONSE] == refreshed_token_response


async def test_coordinator_update_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test coordinator update auth failed setup error."""

    mock_psnawpapi.user.return_value.get_presence.side_effect = (
        PSNAWPAuthenticationError("error msg")
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


async def test_trophy_title_coordinator(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trophy title coordinator updates when PS Vita is registered."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 1

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 2


async def test_trophy_title_coordinator_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trophy title coordinator starts reauth on authentication error."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_psnawpapi.user.return_value.trophy_titles.side_effect = (
        PSNAWPAuthenticationError("error msg")
    )

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


@pytest.mark.parametrize(
    "exception", [PSNAWPNotFoundError, PSNAWPServerError, PSNAWPClientError]
)
async def test_trophy_title_coordinator_update_data_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trophy title coordinator update failed."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_psnawpapi.user.return_value.trophy_titles.side_effect = exception

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    runtime_data: PlaystationNetworkRuntimeData = config_entry.runtime_data
    assert runtime_data.trophy_titles.last_update_success is False


async def test_trophy_title_coordinator_doesnt_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trophy title coordinator does not update if no PS Vita is registered."""

    mock_psnawpapi.me.return_value.get_account_devices.return_value = [
        {"deviceType": "PS5"},
        {"deviceType": "PS3"},
    ]
    mock_psnawpapi.me.return_value.get_profile_legacy.return_value = {
        "profile": {"presences": []}
    }
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 1

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 1


async def test_trophy_title_coordinator_play_new_game(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we play a new game and get a title image on next trophy titles update."""

    _tmp = mock_psnawpapi.user.return_value.trophy_titles.return_value
    mock_psnawpapi.user.return_value.trophy_titles.return_value = []

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 1

    assert (state := hass.states.get("media_player.playstation_vita"))
    assert state.attributes.get("entity_picture") is None

    mock_psnawpapi.user.return_value.trophy_titles.return_value = _tmp

    # Wait one day to trigger PlaystationNetworkTrophyTitlesCoordinator refresh
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Wait another 30 seconds in case the PlaystationNetworkUserDataCoordinator,
    # which has a 30 second update interval, updated before the
    # PlaystationNetworkTrophyTitlesCoordinator.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 2

    assert (state := hass.states.get("media_player.playstation_vita"))
    assert (
        state.attributes["entity_picture"]
        == "https://image.api.playstation.com/trophy/np/NPWR03134_00_0008206095F67FD3BB385E9E00A7C9CFE6F5A4AB96/5F87A6997DD23D1C4D4CC0D1F958ED79CB905331.PNG"
    )


@pytest.mark.parametrize(
    "exception",
    [PSNAWPNotFoundError, PSNAWPServerError, PSNAWPClientError, PSNAWPForbiddenError],
)
async def test_friends_coordinator_update_data_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
) -> None:
    """Test friends coordinator setup fails in _update_data."""

    mock = mock_psnawpapi.user.return_value.friends_list.return_value[0]
    mock.get_presence.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (PSNAWPNotFoundError("error msg"), ConfigEntryState.SETUP_ERROR),
        (PSNAWPAuthenticationError("error msg"), ConfigEntryState.SETUP_ERROR),
        (PSNAWPServerError("error msg"), ConfigEntryState.SETUP_RETRY),
        (PSNAWPClientError("error msg"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_friends_coordinator_setup_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test friends coordinator setup fails in _async_setup."""
    mock = mock_psnawpapi.user.return_value.friends_list.return_value[0]
    mock.profile.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


async def test_friends_coordinator_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test friends coordinator starts reauth on authentication error."""

    mock = mock_psnawpapi.user.return_value.friends_list.return_value[0]
    mock.profile.side_effect = PSNAWPAuthenticationError("error msg")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id
